import logging
import socket
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from ai_it_support_assistant.core.config import Settings
from ai_it_support_assistant.db.session import (
    SessionLocal,
)
from ai_it_support_assistant.repositories.approval_repository import (
    ConcurrentActionUpdateError,
    claim_action_for_execution,
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
    execute_claimed_incident_action as execute_incident_action_service,
)
from ai_it_support_assistant.services.action_payload_service import (
    parse_incident_payload,
    parse_restart_payload,
)
from ai_it_support_assistant.services.authorization_service import (
    authorize_tool,
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

logger = logging.getLogger(__name__)


class ActionAuthorizationError(Exception):
    pass


class UnsupportedActionError(Exception):
    pass


def create_worker_id() -> str:
    hostname = socket.gethostname()
    suffix = uuid4().hex[:8]

    return f"{hostname}-{suffix}"


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

    try:
        authorize_tool(
            tool_name=action.action,
            user=current_user,
        )
    except Exception as exc:
        raise ActionAuthorizationError(
            f"User is no longer authorized to execute action: {action.action}"
        ) from exc

    return current_user


def authorize_restart_action(
    *,
    action: PendingAction,
    user: User,
    settings: Settings,
) -> RestartActionPayload:
    if action.action != "restart_deployment":
        raise ActionAuthorizationError(
            f"Restart authorization was requested for a non-restart action: {action.action}"
        )

    try:
        authorize_tool(
            tool_name="restart_deployment",
            user=user,
        )
    except Exception as exc:
        raise ActionAuthorizationError("User is not authorized to restart deployments.") from exc

    try:
        payload = parse_restart_payload(action.payload_json)
    except Exception as exc:
        raise ActionAuthorizationError("Restart action payload is invalid.") from exc

    if not settings.enable_write_actions:
        raise ActionAuthorizationError("Write actions are disabled.")

    if payload.namespace not in settings.allowed_restart_namespaces:
        raise ActionAuthorizationError(f"Namespace is not allowed: {payload.namespace}")

    if payload.name not in settings.allowed_restart_deployments:
        raise ActionAuthorizationError(f"Deployment is not allowed: {payload.name}")

    return payload


def reconcile_stale_incident_action(
    *,
    action: PendingAction,
    worker_id: str,
    settings: Settings,
) -> None:
    del worker_id  # Reserved for future ownership/audit use.

    idempotency_key = f"create_incident:{action.approval_id}"

    with SessionLocal() as session:
        current_action = get_pending_action(
            session=session,
            approval_id=action.approval_id,
        )

        if current_action is None:
            raise RuntimeError("Pending action disappeared during reconciliation.")

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

        incident = create_incident(
            session=session,
            title=payload.title,
            description=payload.description,
            severity=payload.severity,
            service_name=payload.service_name,
            created_by=current_action.requested_by,
            idempotency_key=idempotency_key,
        )

        mark_action_succeeded(
            session=session,
            approval_id=current_action.approval_id,
            expected_version=current_action.version,
            resource_id=incident.incident_id,
            result_json=None,
        )

        session.commit()


def execute_claimed_restart_action(
    *,
    action: PendingAction,
    worker_id: str,
    settings: Settings,
    session: Session,
) -> None:
    if action is None:
        raise RuntimeError("Pending action disappeared during reconciliation.")
    current_user = load_and_authorize_action_user(
        action=action,
        session=session,
    )

    payload = authorize_restart_action(
        action=action,
        user=current_user,
        settings=settings,
    )

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

    result = monitor_deployment_rollout(
        name=payload.name,
        namespace=payload.namespace,
        timeout_seconds=(settings.restart_timeout_seconds),
        poll_interval_seconds=(settings.restart_poll_interval_seconds),
        max_read_failures=(settings.restart_max_read_failures),
        config_mode=settings.kubernetes_config_mode,
        context=settings.kubernetes_context,
        heartbeat_callback=heartbeat,
    )

    current_action = get_pending_action(
        session=session,
        approval_id=action.approval_id,
    )

    if current_action is None:
        raise RuntimeError("Restart action disappeared during execution.")

    resource_id = f"{payload.namespace}/{payload.name}"

    if result.outcome == "healthy":
        mark_action_succeeded(
            session=session,
            approval_id=current_action.approval_id,
            expected_version=current_action.version,
            resource_id=resource_id,
            result_json=result.model_dump_json(),
        )

        session.commit()
        return

    if result.outcome == "timeout":
        mark_action_failed(
            session=session,
            approval_id=current_action.approval_id,
            expected_version=current_action.version,
            failure_reason="restart_rollout_timeout",
            result_json=result.model_dump_json(),
        )

        session.commit()
        return

    mark_action_failed(
        session=session,
        approval_id=current_action.approval_id,
        expected_version=current_action.version,
        failure_reason="restart_rollout_failed",
        result_json=result.model_dump_json(),
    )

    session.commit()


def reconcile_stale_restart_action(
    *,
    action: PendingAction,
    worker_id: str,
    settings: Settings,
) -> None:
    with SessionLocal() as authorization_session:
        current_user = load_and_authorize_action_user(
            action=action,
            session=authorization_session,
        )

        payload = authorize_restart_action(
            action=action,
            user=current_user,
            settings=settings,
        )

    execution_token = action.execution_token

    if execution_token is None:
        raise RuntimeError("Restart action has no persisted execution token.")
    payload = parse_restart_payload(action.payload_json)

    execution_token = action.execution_token

    if execution_token is None:
        raise RuntimeError("Restart action has no persisted execution token.")

    current_token = get_deployment_restart_token(
        name=payload.name,
        namespace=payload.namespace,
        config_mode=settings.kubernetes_config_mode,
        context=settings.kubernetes_context,
    )

    if current_token != execution_token:
        restart_deployment(
            name=payload.name,
            namespace=payload.namespace,
            execution_token=execution_token,
            config_mode=settings.kubernetes_config_mode,
            context=settings.kubernetes_context,
        )

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

    rollout_result = monitor_deployment_rollout(
        name=payload.name,
        namespace=payload.namespace,
        timeout_seconds=(settings.kubernetes_rollout_timeout_seconds),
        poll_interval_seconds=(settings.kubernetes_rollout_poll_interval_seconds),
        max_read_failures=(settings.kubernetes_rollout_max_read_failures),
        config_mode=(settings.kubernetes_config_mode),
        context=settings.kubernetes_context,
    )

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
                approval_id=current_action.approval_id,
                expected_version=current_action.version,
                resource_id=resource_id,
                result_json=(rollout_result.model_dump_json()),
            )

        elif rollout_result.outcome == "timeout":
            mark_action_failed(
                session=session,
                approval_id=current_action.approval_id,
                expected_version=current_action.version,
                failure_reason=("restart_rollout_timeout"),
                result_json=(rollout_result.model_dump_json()),
            )

        else:
            mark_action_failed(
                session=session,
                approval_id=current_action.approval_id,
                expected_version=current_action.version,
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
    """

    if action.state != "executing":
        raise RuntimeError(
            f"Only executing actions may be dispatched. Current state: {action.state}"
        )

    current_user = load_and_authorize_action_user(
        action=action,
        session=session,
    )

    if action.action == "create_incident":
        execute_incident_action_service(
            session=session,
            approval_id=action.approval_id,
            current_user=current_user,
            worker_id=worker_id,
        )
        return

    if action.action == "restart_deployment":
        execute_claimed_restart_action(
            session=session,
            approval_id=action.approval_id,
            current_user=current_user,
            worker_id=worker_id,
            settings=settings,
        )
        return

    raise RuntimeError(f"Unsupported action type: {action.action}")


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
            continue

        try:
            with SessionLocal() as execution_session:
                current_action = get_pending_action(
                    session=execution_session,
                    approval_id=claimed_action.approval_id,
                )

                if current_action is None:
                    raise RuntimeError("Claimed action disappeared before execution.")

                execute_claimed_action(
                    action=current_action,
                    worker_id=worker_id,
                    settings=settings,
                    session=execution_session,
                )

            processed += 1

        except Exception:
            logger.exception(
                "action_execution_failed",
                extra={
                    "approval_id": claimed_action.approval_id,
                    "worker_id": worker_id,
                    "action": claimed_action.action,
                },
            )

            handle_action_execution_failure(
                approval_id=claimed_action.approval_id,
            )

            processed += 1

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
            continue

        try:
            reconcile_claimed_stale_action(
                action=reclaimed_action,
                worker_id=worker_id,
                settings=settings,
            )

            recovered += 1

        except Exception:
            logger.exception(
                "stale_action_reconciliation_failed",
                extra={
                    "approval_id": reclaimed_action.approval_id,
                    "worker_id": worker_id,
                    "action": reclaimed_action.action,
                },
            )

            handle_action_execution_failure(
                approval_id=reclaimed_action.approval_id,
                failure_reason="stale_action_reconciliation_failed",
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
    """

    worker_id = create_worker_id()

    logger.info(
        "action_worker_started",
        extra={
            "worker_id": worker_id,
        },
    )

    try:
        while True:
            try:
                recovered = reconcile_stale_actions(
                    worker_id=worker_id,
                    settings=settings,
                )

                processed = run_worker_once(
                    worker_id=worker_id,
                    settings=settings,
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

            time.sleep(settings.action_worker_poll_interval_seconds)
    except KeyboardInterrupt:
        logger.info(
            "action_worker_stopping",
            extra={
                "worker_id": worker_id,
            },
        )
