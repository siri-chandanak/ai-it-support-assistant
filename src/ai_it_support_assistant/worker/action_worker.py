import logging
import signal
import socket
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from opentelemetry.trace import Status, StatusCode
from sqlalchemy.orm import Session

from ai_it_support_assistant.core.config import Settings
from ai_it_support_assistant.db.session import (
    SessionLocal,
)
from ai_it_support_assistant.observability.metrics import (
    ACTION_EXECUTION_DURATION,
    ACTION_QUEUE_DELAY,
    ACTION_QUEUE_DEPTH,
    ACTION_STATE_TRANSITIONS,
    WORKER_ACTIONS_CLAIMED,
    WORKER_ACTIONS_FAILED,
    WORKER_ACTIONS_SUCCEEDED,
    WORKER_CLAIM_CONFLICTS,
    WORKER_STALE_ACTIONS_RECOVERED,
)
from ai_it_support_assistant.observability.tracing import (
    get_tracer,
)
from ai_it_support_assistant.repositories.approval_repository import (
    ConcurrentActionUpdateError,
    claim_action_for_execution,
    count_actions_by_state,
    get_pending_action,
    list_approved_actions,
    list_stale_executing_actions,
    mark_action_failed,
    mark_action_succeeded,
    reclaim_stale_action,
    update_action_heartbeat,
)
from ai_it_support_assistant.repositories.incident_repository import (
    get_incident_by_idempotency_key,
)
from ai_it_support_assistant.repositories.user_repository import (
    get_user_by_username,
)
from ai_it_support_assistant.schemas.approval import (
    PendingAction,
    RestartActionPayload,
)
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.services.action_execution_service import (
    execute_claimed_incident_action,
)
from ai_it_support_assistant.services.action_execution_service import (
    execute_claimed_restart_action as execute_restart_action_service,
)
from ai_it_support_assistant.services.action_payload_service import (
    parse_incident_payload,
    parse_restart_payload,
)
from ai_it_support_assistant.services.incident_service import (
    create_incident,
)
from ai_it_support_assistant.services.kubernetes_rollout_service import (
    get_deployment_restart_token,
    monitor_deployment_rollout,
)
from ai_it_support_assistant.services.kubernetes_write_service import (
    restart_deployment,
)
from ai_it_support_assistant.services.policy_authorization_service import (
    authorize_deployment_restart,
    authorize_incident_create,
    build_policy_subject,
)
from ai_it_support_assistant.services.policy_enforcement_service import (
    enforce_policy,
)
from ai_it_support_assistant.worker.metrics import (
    refresh_action_queue_metrics,
)

logger = logging.getLogger(__name__)

tracer = get_tracer()


class ActionAuthorizationError(Exception):
    pass


class UnsupportedActionError(Exception):
    pass


def create_worker_id() -> str:
    hostname = socket.gethostname()
    suffix = uuid4().hex[:8]

    return f"{hostname}-{suffix}"


def get_worker_metric_failure_reason(
    failure_reason: str | None,
) -> str:
    """Map action failures to bounded Prometheus label values."""

    mapping = {
        "restart_rollout_timeout": "rollout_timeout",
        "restart_rollout_failed": "rollout_failed",
        "action_execution_failed": "execution_error",
        "stale_action_reconciliation_failed": "stale_reconciliation_failed",
    }

    if failure_reason is None:
        return "action_failed"

    return mapping.get(
        failure_reason,
        "action_failed",
    )


def record_terminal_action_metric(
    action: PendingAction,
) -> str:
    """Record a terminal worker result and return its metric outcome."""

    if action.state == "succeeded":
        WORKER_ACTIONS_SUCCEEDED.labels(
            action_type=action.action,
        ).inc()

        return "success"

    if action.state == "failed":
        WORKER_ACTIONS_FAILED.labels(
            action_type=action.action,
            failure_reason=get_worker_metric_failure_reason(action.failure_reason),
        ).inc()

        return "failure"

    raise RuntimeError(f"Action execution returned with unexpected state: {action.state}")


def add_action_trace_attributes(
    *,
    span,
    action: PendingAction,
    worker_id: str,
) -> None:
    span.set_attribute(
        "action.type",
        action.action,
    )

    span.set_attribute(
        "action.state",
        action.state,
    )

    span.set_attribute(
        "action.approval_id",
        action.approval_id,
    )

    span.set_attribute(
        "worker.id",
        worker_id,
    )

    origin_trace_id = getattr(
        action,
        "origin_trace_id",
        None,
    )

    if origin_trace_id:
        span.set_attribute(
            "origin.trace_id",
            origin_trace_id,
        )

    origin_request_id = getattr(
        action,
        "origin_request_id",
        None,
    )

    if origin_request_id:
        span.set_attribute(
            "origin.request_id",
            origin_request_id,
        )


def load_and_authorize_action_user(
    *,
    action: PendingAction,
    session: Session,
) -> User:
    user = get_user_by_username(
        db=session,
        username=action.requested_by,
    )

    if user is None:
        raise ActionAuthorizationError("Requested user no longer exists.")

    if user.disabled:
        raise ActionAuthorizationError("Requested user is disabled.")

    current_user = User(
        user_id=str(user.id),
        username=user.username,
        roles=user.roles,
        disabled=user.disabled,
    )

    return current_user


def parse_restart_action(
    *,
    action: PendingAction,
) -> RestartActionPayload:
    if action.action != "restart_deployment":
        raise ActionAuthorizationError(
            f"Restart authorization was requested for a non-restart action: {action.action}"
        )

    try:
        payload = parse_restart_payload(action.payload_json)
    except Exception as exc:
        raise ActionAuthorizationError("Restart action payload is invalid.") from exc

    return payload


def reconcile_stale_incident_action(
    *,
    action: PendingAction,
    worker_id: str,
    settings: Settings,
) -> None:
    del worker_id
    del settings

    idempotency_key = f"create_incident:{action.approval_id}"

    with SessionLocal() as session:
        current_action = get_pending_action(
            session=session,
            approval_id=action.approval_id,
        )

        if current_action is None:
            raise RuntimeError("Pending action disappeared during reconciliation.")

        current_user = load_and_authorize_action_user(
            session=session,
            action=current_action,
        )

        if current_user is None:
            raise RuntimeError("Requesting user could not be loaded during reconciliation.")

        subject = build_policy_subject(current_user)

        policy_decision = authorize_incident_create(
            subject=subject,
            phase="reconciliation",
            approval_state=None,
            session=session,
        )

        enforce_policy(policy_decision)

        existing_incident_id = get_incident_by_idempotency_key(
            session=session,
            idempotency_key=idempotency_key,
        )

        if existing_incident_id is not None:
            mark_action_succeeded(
                session=session,
                approval_id=current_action.approval_id,
                expected_version=current_action.version,
                resource_id=existing_incident_id,
                result_json=None,
            )

            session.commit()
            return

        payload = parse_incident_payload(current_action.payload_json)

        execution_result = create_incident(
            session=session,
            request=payload,
            created_by=current_action.requested_by,
            idempotency_key=idempotency_key,
        )

        mark_action_succeeded(
            session=session,
            approval_id=current_action.approval_id,
            expected_version=current_action.version,
            resource_id=execution_result.incident.incident_id,
            result_json=None,
        )

        session.commit()


# def execute_claimed_restart_action(
#     *,
#     action: PendingAction,
#     worker_id: str,
#     settings: Settings,
#     session: Session,
# ) -> None:
#     if action is None:
#         raise RuntimeError("Pending action disappeared during reconciliation.")
#     _current_user = load_and_authorize_action_user(
#         action=action,
#         session=session,
#     )

#     payload = parse_restart_action(
#         action=action,
#     )

#     def heartbeat() -> None:
#         with SessionLocal() as heartbeat_session:
#             updated = update_action_heartbeat(
#                 session=heartbeat_session,
#                 approval_id=action.approval_id,
#                 worker_id=worker_id,
#             )

#             if updated:
#                 heartbeat_session.commit()
#             else:
#                 heartbeat_session.rollback()

#     result = monitor_deployment_rollout(
#         name=payload.name,
#         namespace=payload.namespace,
#         timeout_seconds=settings.kubernetes_rollout_timeout_seconds,
#         poll_interval_seconds=settings.kubernetes_rollout_poll_interval_seconds,
#         max_read_failures=settings.kubernetes_rollout_max_read_failures,
#         config_mode=settings.kubernetes_config_mode,
#         context=settings.kubernetes_context,
#         heartbeat_callback=heartbeat,
#     )

#     current_action = get_pending_action(
#         session=session,
#         approval_id=action.approval_id,
#     )

#     if current_action is None:
#         raise RuntimeError("Restart action disappeared during execution.")

#     resource_id = f"{payload.namespace}/{payload.name}"

#     if result.outcome == "healthy":
#         mark_action_succeeded(
#             session=session,
#             approval_id=current_action.approval_id,
#             expected_version=current_action.version,
#             resource_id=resource_id,
#             result_json=result.model_dump_json(),
#         )

#         session.commit()
#         return

#     if result.outcome == "timeout":
#         mark_action_failed(
#             session=session,
#             approval_id=current_action.approval_id,
#             expected_version=current_action.version,
#             failure_reason="restart_rollout_timeout",
#             result_json=result.model_dump_json(),
#         )

#         session.commit()
#         return

#     mark_action_failed(
#         session=session,
#         approval_id=current_action.approval_id,
#         expected_version=current_action.version,
#         failure_reason="restart_rollout_failed",
#         result_json=result.model_dump_json(),
#     )

#     session.commit()


def reconcile_stale_restart_action(
    *,
    action: PendingAction,
    worker_id: str,
    settings: Settings,
) -> None:
    #
    # Re-authorize the stale execution using
    # CURRENT user identity, permissions, configuration,
    # and resource grants.
    #
    with SessionLocal() as authorization_session:
        current_user = load_and_authorize_action_user(
            action=action,
            session=authorization_session,
        )

        payload = parse_restart_payload(action.payload_json)

        subject = build_policy_subject(current_user)

        policy_decision = authorize_deployment_restart(
            subject=subject,
            namespace=payload.namespace,
            deployment_name=payload.name,
            phase="reconciliation",
            writes_enabled=(settings.kubernetes_write_enabled),
            allowed_namespaces=(settings.kubernetes_restart_allowed_namespaces),
            allowed_deployments=(settings.kubernetes_restart_allowed_deployments),
            approval_state=None,
            session=authorization_session,
        )

        enforce_policy(policy_decision)

    #
    # A stale restart must already have a persisted
    # execution token.
    #
    # Never generate a new token during reconciliation.
    #
    execution_token = action.execution_token

    if execution_token is None:
        raise RuntimeError("Restart action has no persisted execution token.")

    #
    # Check authoritative Kubernetes state.
    #
    # If Kubernetes already contains our persisted token,
    # the original restart was applied and we MUST NOT
    # issue another patch.
    #
    current_token = get_deployment_restart_token(
        name=payload.name,
        namespace=payload.namespace,
        config_mode=(settings.kubernetes_config_mode),
        context=settings.kubernetes_context,
    )

    #
    # The original worker may have crashed before
    # Kubernetes received the restart patch.
    #
    # Reuse the SAME persisted execution token.
    #
    if current_token != execution_token:
        restart_deployment(
            name=payload.name,
            namespace=payload.namespace,
            restart_timestamp=execution_token,
            config_mode=(settings.kubernetes_config_mode),
            context=settings.kubernetes_context,
        )

    #
    # Heartbeat callback for long-running reconciliation.
    #
    def heartbeat() -> None:
        with SessionLocal() as heartbeat_session:
            updated = update_action_heartbeat(
                session=heartbeat_session,
                approval_id=action.approval_id,
                worker_id=worker_id,
            )

            if updated:
                heartbeat_session.commit()
            else:
                heartbeat_session.rollback()

    #
    # Continue monitoring the existing restart.
    #
    rollout_result = monitor_deployment_rollout(
        name=payload.name,
        namespace=payload.namespace,
        timeout_seconds=(settings.kubernetes_rollout_timeout_seconds),
        poll_interval_seconds=(settings.kubernetes_rollout_poll_interval_seconds),
        max_read_failures=(settings.kubernetes_rollout_max_read_failures),
        config_mode=(settings.kubernetes_config_mode),
        context=settings.kubernetes_context,
        heartbeat_callback=heartbeat,
    )

    #
    # Finalize the reclaimed action.
    #
    with SessionLocal() as session:
        current_action = get_pending_action(
            session=session,
            approval_id=action.approval_id,
        )

        if current_action is None:
            raise RuntimeError("Restart action disappeared.")

        resource_id = f"{payload.namespace}/{payload.name}"

        if rollout_result.outcome == "healthy":
            mark_action_succeeded(
                session=session,
                approval_id=(current_action.approval_id),
                expected_version=(current_action.version),
                resource_id=resource_id,
                result_json=(rollout_result.model_dump_json()),
            )

        elif rollout_result.outcome == "timeout":
            mark_action_failed(
                session=session,
                approval_id=(current_action.approval_id),
                expected_version=(current_action.version),
                failure_reason=("restart_rollout_timeout"),
                result_json=(rollout_result.model_dump_json()),
            )

        else:
            mark_action_failed(
                session=session,
                approval_id=(current_action.approval_id),
                expected_version=(current_action.version),
                failure_reason=("restart_rollout_failed"),
                result_json=(rollout_result.model_dump_json()),
            )

        session.commit()


def execute_claimed_action(
    *,
    action: PendingAction,
    worker_id: str,
    settings: Settings,
    session: Session,
) -> None:
    """
    Dispatch an already-claimed action to its executor.

    The action MUST already be in state="executing".
    This function does not claim the action.

    This is also the high-level observability boundary for worker
    action success/failure metrics.
    """

    if action.state != "executing":
        raise RuntimeError(
            f"Only executing actions may be dispatched. Current state: {action.state}"
        )

    try:
        # Re-load the current user and re-authorize immediately
        # before performing the operational action.
        current_user = load_and_authorize_action_user(
            action=action,
            session=session,
        )

        if action.action == "create_incident":
            execute_claimed_incident_action(
                session=session,
                approval_id=action.approval_id,
                current_user=current_user,
                worker_id=worker_id,
            )

        elif action.action == "restart_deployment":
            execute_restart_action_service(
                session=session,
                approval_id=action.approval_id,
                current_user=current_user,
                worker_id=worker_id,
                settings=settings,
            )

        else:
            raise UnsupportedActionError(f"Unsupported action type: {action.action}")

    except UnsupportedActionError:
        WORKER_ACTIONS_FAILED.labels(
            action_type=action.action,
            failure_reason="unsupported_action",
        ).inc()

        logger.exception(
            "action_execution_failed",
            extra={
                "approval_id": action.approval_id,
                "action_type": action.action,
                "failure_reason": "unsupported_action",
                "worker_id": worker_id,
            },
        )

        raise

    except Exception:
        WORKER_ACTIONS_FAILED.labels(
            action_type=action.action,
            failure_reason="unknown_internal_error",
        ).inc()

        logger.exception(
            "action_execution_failed",
            extra={
                "approval_id": action.approval_id,
                "action_type": action.action,
                "failure_reason": "unknown_internal_error",
                "worker_id": worker_id,
            },
        )

        raise

    else:
        WORKER_ACTIONS_SUCCEEDED.labels(
            action_type=action.action,
        ).inc()

        logger.info(
            "action_execution_succeeded",
            extra={
                "approval_id": action.approval_id,
                "action_type": action.action,
                "worker_id": worker_id,
            },
        )


def handle_action_execution_failure(
    *,
    approval_id: str,
    failure_reason: str = "action_execution_failed",
) -> None:
    """
    Best-effort transition of an executing action to failed.

    Uses a fresh session because the execution session may
    already be in a failed/rolled-back state.
    """

    with SessionLocal() as session:
        action = get_pending_action(
            session=session,
            approval_id=approval_id,
        )

        if action is None:
            return

        if action.state != "executing":
            return

        try:
            mark_action_failed(
                session=session,
                approval_id=action.approval_id,
                expected_version=action.version,
                failure_reason=failure_reason,
                result_json=None,
            )

            session.commit()

        except ConcurrentActionUpdateError:
            session.rollback()


def run_worker_once(
    *,
    worker_id: str,
    settings: Settings,
) -> int:
    """
    Process at most action_worker_batch_size approved actions.

    Returns the number of actions successfully claimed
    for processing by this worker.
    """

    with SessionLocal() as discovery_session:
        actions = list_approved_actions(
            session=discovery_session,
            limit=settings.action_worker_batch_size,
        )

    processed = 0

    for candidate in actions:
        try:
            with SessionLocal() as claim_session:
                claim_action_for_execution(
                    session=claim_session,
                    approval_id=candidate.approval_id,
                    expected_version=candidate.version,
                    worker_id=worker_id,
                )

                claim_session.commit()

                claimed_action = get_pending_action(
                    session=claim_session,
                    approval_id=candidate.approval_id,
                )

                if claimed_action is None:
                    raise RuntimeError("Claimed action could not be reloaded.")

        except ConcurrentActionUpdateError:
            # Another worker won the race.
            WORKER_CLAIM_CONFLICTS.labels(
                action_type=candidate.action,
            ).inc()

            continue

        WORKER_ACTIONS_CLAIMED.labels(
            action_type=claimed_action.action,
        ).inc()

        ACTION_STATE_TRANSITIONS.labels(
            action_type=claimed_action.action,
            from_state="approved",
            to_state="executing",
        ).inc()

        if (
            claimed_action.approved_at is not None
            and claimed_action.execution_started_at is not None
        ):
            queue_delay = (
                claimed_action.execution_started_at - claimed_action.approved_at
            ).total_seconds()

            ACTION_QUEUE_DELAY.labels(
                action_type=claimed_action.action,
            ).observe(max(queue_delay, 0.0))

        execution_start = time.perf_counter()
        outcome = "failure"
        _terminal_metric_recorded = False

        try:
            with tracer.start_as_current_span("worker.action.execute") as span:
                try:
                    add_action_trace_attributes(
                        span=span,
                        action=claimed_action,
                        worker_id=worker_id,
                    )

                    span.add_event("worker_claimed")

                    with SessionLocal() as execution_session:
                        current_action = get_pending_action(
                            session=execution_session,
                            approval_id=(claimed_action.approval_id),
                        )

                        if current_action is None:
                            raise RuntimeError("Claimed action disappeared before execution.")

                        execute_claimed_action(
                            action=current_action,
                            worker_id=worker_id,
                            settings=settings,
                            session=execution_session,
                        )

                    span.add_event("action_execution_completed")

                except Exception as exc:
                    span.record_exception(exc)

                    span.set_status(
                        Status(
                            StatusCode.ERROR,
                            "worker action execution failed",
                        )
                    )

                    raise

            outcome = "success"

            processed += 1

        except Exception:
            logger.exception(
                "action_execution_failed",
                extra={
                    "approval_id": (claimed_action.approval_id),
                    "worker_id": worker_id,
                    "action": claimed_action.action,
                },
            )

            handle_action_execution_failure(
                approval_id=(claimed_action.approval_id),
            )

            processed += 1

        finally:
            ACTION_EXECUTION_DURATION.labels(
                action_type=claimed_action.action,
                outcome=outcome,
            ).observe(time.perf_counter() - execution_start)

    return processed


def reconcile_claimed_stale_action(
    *,
    action: PendingAction,
    worker_id: str,
    settings: Settings,
) -> None:
    """
    Reconcile an executing action that has already been
    reclaimed by this worker.
    """

    if action.action == "create_incident":
        reconcile_stale_incident_action(
            action=action,
            worker_id=worker_id,
            settings=settings,
        )
        return

    if action.action == "restart_deployment":
        reconcile_stale_restart_action(
            action=action,
            worker_id=worker_id,
            settings=settings,
        )
        return

    raise UnsupportedActionError(f"Unsupported stale action: {action.action}")


def reconcile_stale_actions(
    *,
    worker_id: str,
    settings: Settings,
) -> int:
    """
    Find stale executing actions, atomically reclaim them,
    and perform action-specific reconciliation.
    """

    stale_before = datetime.now(UTC) - timedelta(
        seconds=(settings.action_worker_stale_after_seconds)
    )

    with SessionLocal() as discovery_session:
        stale_actions = list_stale_executing_actions(
            session=discovery_session,
            stale_before=stale_before,
            limit=settings.action_worker_batch_size,
        )

    recovered = 0

    for candidate in stale_actions:
        try:
            with SessionLocal() as reclaim_session:
                reclaim_stale_action(
                    session=reclaim_session,
                    approval_id=candidate.approval_id,
                    expected_version=candidate.version,
                    stale_before=stale_before,
                    worker_id=worker_id,
                )

                reclaim_session.commit()

                reclaimed_action = get_pending_action(
                    session=reclaim_session,
                    approval_id=candidate.approval_id,
                )

                if reclaimed_action is None:
                    raise RuntimeError("Reclaimed action could not be reloaded.")

        except ConcurrentActionUpdateError:
            # Another worker reclaimed it first.
            WORKER_CLAIM_CONFLICTS.labels(
                action_type=candidate.action,
            ).inc()

            continue

        try:
            with tracer.start_as_current_span("worker.reconcile_action") as span:
                add_action_trace_attributes(
                    span=span,
                    action=reclaimed_action,
                    worker_id=worker_id,
                )

                span.add_event("worker_reclaimed_stale_action")

                reconcile_claimed_stale_action(
                    action=reclaimed_action,
                    worker_id=worker_id,
                    settings=settings,
                )

                with SessionLocal() as result_session:
                    final_action = get_pending_action(
                        session=result_session,
                        approval_id=(reclaimed_action.approval_id),
                    )

                    if final_action is None:
                        raise RuntimeError("Reconciled action disappeared.")

                    reconciliation_outcome = record_terminal_action_metric(final_action)

                WORKER_STALE_ACTIONS_RECOVERED.labels(
                    action_type=reclaimed_action.action,
                ).inc()

                span.add_event(
                    "action_reconciliation_completed",
                    {
                        "outcome": reconciliation_outcome,
                    },
                )

            recovered += 1

        except Exception:
            WORKER_ACTIONS_FAILED.labels(
                action_type=reclaimed_action.action,
                failure_reason="stale_reconciliation_failed",
            ).inc()

            logger.exception(
                "stale_action_reconciliation_failed",
                extra={
                    "approval_id": (reclaimed_action.approval_id),
                    "worker_id": worker_id,
                    "action": reclaimed_action.action,
                },
            )

            handle_action_execution_failure(
                approval_id=(reclaimed_action.approval_id),
                failure_reason=("stale_action_reconciliation_failed"),
            )

            recovered += 1

    return recovered


def run_action_worker(
    *,
    settings: Settings,
) -> None:
    """
    Continuously recover stale work and process
    newly approved actions.

    Handles SIGTERM/SIGINT gracefully so Kubernetes
    can stop the worker without immediately killing
    an in-progress worker iteration.
    """

    worker_id = create_worker_id()

    shutdown_requested = False

    def handle_shutdown_signal(
        signum: int,
        _frame: object,
    ) -> None:
        nonlocal shutdown_requested

        logger.info(
            "action_worker_shutdown_requested",
            extra={
                "worker_id": worker_id,
                "signal": signum,
            },
        )

        shutdown_requested = True

    signal.signal(
        signal.SIGTERM,
        handle_shutdown_signal,
    )

    signal.signal(
        signal.SIGINT,
        handle_shutdown_signal,
    )

    logger.info(
        "action_worker_started",
        extra={
            "worker_id": worker_id,
        },
    )

    while not shutdown_requested:
        try:
            # Refresh DB-backed Prometheus gauges before
            # processing this worker iteration.
            with SessionLocal() as session:
                refresh_action_queue_metrics(
                    session=session,
                )

            recovered = reconcile_stale_actions(
                worker_id=worker_id,
                settings=settings,
            )

            processed = run_worker_once(
                worker_id=worker_id,
                settings=settings,
            )

            # Action states may have changed during this iteration:
            #
            # approved -> executing
            # executing -> succeeded
            # executing -> failed
            #
            # Refresh metrics again so Prometheus reflects
            # the latest PostgreSQL state.
            with SessionLocal() as session:
                refresh_action_queue_metrics(
                    session=session,
                )

            logger.debug(
                "action_worker_iteration_completed",
                extra={
                    "worker_id": worker_id,
                    "stale_actions_recovered": recovered,
                    "approved_actions_processed": processed,
                },
            )

        except Exception:
            logger.exception(
                "action_worker_iteration_failed",
                extra={
                    "worker_id": worker_id,
                },
            )

        if shutdown_requested:
            break

        time.sleep(
            settings.action_worker_poll_interval_seconds,
        )

    logger.info(
        "action_worker_stopped",
        extra={
            "worker_id": worker_id,
        },
    )


def update_queue_depth_metric(
    session: Session,
) -> None:
    approved_count = count_actions_by_state(
        session,
        "approved",
    )

    ACTION_QUEUE_DEPTH.set(approved_count)
