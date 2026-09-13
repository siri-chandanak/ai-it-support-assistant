import logging

from sqlalchemy.orm import Session

from ai_it_support_assistant.core.config import Settings
from ai_it_support_assistant.repositories.approval_repository import (
    ConcurrentActionUpdateError,
    get_pending_action,
    mark_action_failed,
    mark_action_succeeded,
)
from ai_it_support_assistant.repositories.incident_repository import (
    get_incident,
)
from ai_it_support_assistant.schemas.approval import (
    PendingAction,
)
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.schemas.incident import (
    IncidentRecord,
)
from ai_it_support_assistant.schemas.kubernetes import (
    DeploymentRestartExecutionResult,
)
from ai_it_support_assistant.services.action_payload_service import (
    parse_incident_payload,
    parse_restart_payload,
)
from ai_it_support_assistant.services.approval_service import (
    ensure_execution_token,
)
from ai_it_support_assistant.services.audit_service import (
    record_audit_event,
)
from ai_it_support_assistant.services.authorization_service import (
    authorize_tool,
)
from ai_it_support_assistant.services.incident_service import (
    create_incident,
)
from ai_it_support_assistant.services.kubernetes_rollout_service import (
    monitor_deployment_rollout,
)
from ai_it_support_assistant.services.kubernetes_state_service import (
    KubernetesResourceNotFoundError,
    get_deployment_state,
)
from ai_it_support_assistant.services.kubernetes_write_policy_service import (
    validate_restart_policy,
)
from ai_it_support_assistant.services.kubernetes_write_service import (
    KubernetesWriteError,
    deployment_has_restart_token,
    restart_deployment,
)

logger = logging.getLogger(__name__)


class ApprovalOwnershipError(Exception):
    pass


class ActionNotApprovedError(Exception):
    pass


class ActionRejectedError(Exception):
    pass


class ActionExecutionError(Exception):
    pass


class ActionCurrentlyExecutingError(Exception):
    pass


class ActionFailedError(Exception):
    pass


class IncidentExecutionError(Exception):
    pass


class KubernetesRestartExecutionError(ActionExecutionError):
    pass


class UnsupportedActionError(ActionExecutionError):
    pass


def _audit_execution_started(
    *,
    session: Session,
    approval_id: str,
    action_type: str,
    actor: str,
    resource_id: str | None = None,
) -> None:
    record_audit_event(
        session=session,
        event_type="ACTION_EXECUTION_STARTED",
        actor=actor,
        action_type=action_type,
        approval_id=approval_id,
        resource_id=resource_id,
        details={
            "previous_state": "approved",
            "new_state": "executing",
        },
    )


def _audit_execution_succeeded(
    *,
    session: Session,
    approval_id: str,
    action_type: str,
    resource_id: str | None,
    actor: str,
) -> None:
    record_audit_event(
        session=session,
        event_type="ACTION_EXECUTED",
        actor=actor,
        action_type=action_type,
        approval_id=approval_id,
        resource_id=resource_id,
        details={
            "previous_state": "executing",
            "new_state": "succeeded",
        },
    )


def _audit_execution_failed(
    *,
    session: Session,
    approval_id: str,
    action_type: str,
    actor: str,
    resource_id: str | None = None,
) -> None:
    record_audit_event(
        session=session,
        event_type="ACTION_EXECUTION_FAILED",
        actor=actor,
        action_type=action_type,
        approval_id=approval_id,
        resource_id=resource_id,
        details={
            "previous_state": "executing",
            "new_state": "failed",
        },
    )


def _audit_restart_applied(
    *,
    session: Session,
    approval_id: str,
    actor: str,
    resource_id: str,
    namespace: str,
    deployment_name: str,
) -> None:
    record_audit_event(
        session=session,
        event_type="KUBERNETES_RESTART_APPLIED",
        actor=actor,
        action_type="restart_deployment",
        approval_id=approval_id,
        resource_id=resource_id,
        details={
            "namespace": namespace,
            "deployment": deployment_name,
        },
    )


def _audit_rollout_monitor_started(
    *,
    session: Session,
    approval_id: str,
    actor: str,
    resource_id: str,
    namespace: str,
    deployment_name: str,
) -> None:
    record_audit_event(
        session=session,
        event_type="ROLLOUT_MONITOR_STARTED",
        actor=actor,
        action_type="restart_deployment",
        approval_id=approval_id,
        resource_id=resource_id,
        details={
            "namespace": namespace,
            "deployment": deployment_name,
        },
    )


def _audit_rollout_result(
    *,
    session: Session,
    approval_id: str,
    actor: str,
    resource_id: str,
    namespace: str,
    deployment_name: str,
    event_type: str,
    desired_replicas: int,
    updated_replicas: int,
    ready_replicas: int,
    available_replicas: int,
) -> None:
    record_audit_event(
        session=session,
        event_type=event_type,
        actor=actor,
        action_type="restart_deployment",
        approval_id=approval_id,
        resource_id=resource_id,
        details={
            "namespace": namespace,
            "deployment": deployment_name,
            "desired_replicas": str(desired_replicas),
            "updated_replicas": str(updated_replicas),
            "ready_replicas": str(ready_replicas),
            "available_replicas": str(available_replicas),
        },
    )


def _validate_action_for_execution(
    *,
    action: PendingAction,
    current_user: User,
) -> None:
    if action.requested_by != current_user.username:
        raise ApprovalOwnershipError("You cannot execute another user's approval.")

    if action.state == "pending":
        raise ActionNotApprovedError("Action has not been approved.")

    if action.state == "rejected":
        raise ActionRejectedError("Action was rejected.")

    if action.state == "executing":
        raise ActionCurrentlyExecutingError("Action is already being executed.")

    if action.state == "failed":
        raise ActionFailedError("Action previously failed and cannot be retried automatically.")

    if action.state != "approved":
        raise ActionNotApprovedError(f"Action cannot execute from state: {action.state}")


def _validate_claimed_action_for_execution(
    *,
    action: PendingAction,
    current_user: User,
    worker_id: str,
    execution_error_type: type[Exception],
) -> None:
    if action.requested_by != current_user.username:
        raise ApprovalOwnershipError("You cannot execute another user's approval.")

    if action.state == "pending":
        raise ActionNotApprovedError("Action has not been approved.")

    if action.state == "rejected":
        raise ActionRejectedError("Action was rejected.")

    if action.state == "failed":
        raise ActionFailedError("Action previously failed and cannot be retried automatically.")

    if action.state == "approved":
        raise execution_error_type("Action must be claimed by a worker before execution.")

    if action.state != "executing":
        raise execution_error_type(f"Action cannot execute from state: {action.state}")

    if action.worker_id != worker_id:
        raise execution_error_type("Action is owned by another worker.")


def execute_claimed_incident_action(
    *,
    session: Session,
    approval_id: str,
    current_user: User,
    worker_id: str,
) -> IncidentRecord:
    action = get_pending_action(
        session=session,
        approval_id=approval_id,
    )

    if action is None:
        raise ValueError(f"Approval not found: {approval_id}")

    if action.action != "create_incident":
        raise IncidentExecutionError("Approval is not a create_incident action.")

    if action.requested_by != current_user.username:
        raise ApprovalOwnershipError("You cannot execute another user's approval.")

    #
    # Re-authorize using the user's CURRENT roles.
    #
    authorize_tool(
        tool_name="create_incident",
        user=current_user,
    )

    #
    # Idempotent read-after-success behavior.
    #
    # If this action already succeeded, do NOT create
    # another incident.
    #
    if action.state == "succeeded":
        if action.resource_id is None:
            raise IncidentExecutionError("Succeeded action is missing resource ID.")

        incident = get_incident(
            session=session,
            incident_id=action.resource_id,
        )

        if incident is None:
            raise IncidentExecutionError("Existing incident could not be found.")

        return incident

    #
    # The worker must already have claimed this action.
    #
    _validate_claimed_action_for_execution(
        action=action,
        current_user=current_user,
        worker_id=worker_id,
        execution_error_type=IncidentExecutionError,
    )

    incident_request = parse_incident_payload(action.payload_json)

    #
    # Record that execution has started.
    #
    _audit_execution_started(
        session=session,
        approval_id=approval_id,
        action_type="create_incident",
        actor=current_user.username,
    )

    #
    # Persist audit/state-related work before performing
    # the external operation.
    #
    session.commit()

    #
    # Stable idempotency key.
    #
    # If the worker crashes and later reconciles/retries,
    # the same approval must always use the same key.
    #
    idempotency_key = f"create_incident:{approval_id}"

    try:
        execution_result = create_incident(
            session=session,
            request=incident_request,
            created_by=current_user.username,
            idempotency_key=idempotency_key,
        )

        incident = execution_result.incident

    except Exception:
        #
        # External incident creation failed.
        #
        session.rollback()

        current_action = get_pending_action(
            session=session,
            approval_id=approval_id,
        )

        if current_action is None:
            raise IncidentExecutionError(
                "Incident creation failed and approval could not be reloaded."
            ) from None

        try:
            mark_action_failed(
                session=session,
                approval_id=approval_id,
                expected_version=current_action.version,
                failure_reason="incident_creation_failed",
            )

            _audit_execution_failed(
                session=session,
                approval_id=approval_id,
                action_type="create_incident",
                actor=current_user.username,
            )

            session.commit()

            #
            # Ensure later reads see the updated state.
            #
            session.expire_all()

        except ConcurrentActionUpdateError:
            session.rollback()

        raise IncidentExecutionError("Incident creation failed.") from None

    #
    # Ensure anything created by create_incident()
    # is flushed before finalizing the action.
    #
    session.flush()

    current_action = get_pending_action(
        session=session,
        approval_id=approval_id,
    )

    if current_action is None:
        session.rollback()

        raise IncidentExecutionError("Incident was created but approval could not be reloaded.")

    #
    # Finalize executing -> succeeded.
    #
    try:
        mark_action_succeeded(
            session=session,
            approval_id=approval_id,
            expected_version=current_action.version,
            resource_id=incident.incident_id,
        )

        #
        # Flush the conditional UPDATE before creating
        # the audit record.
        #
        session.flush()

    except ConcurrentActionUpdateError as exc:
        session.rollback()

        raise IncidentExecutionError(
            "Incident was created but action state could not be finalized."
        ) from exc

    #
    # Record successful execution.
    #
    _audit_execution_succeeded(
        session=session,
        approval_id=approval_id,
        action_type="create_incident",
        resource_id=incident.incident_id,
        actor=current_user.username,
    )

    #
    # Commit both:
    #   executing -> succeeded
    #   success audit event
    #
    session.commit()

    #
    # Important:
    #
    # mark_action_succeeded() uses a conditional UPDATE.
    # SQLAlchemy may still hold an older ORM instance
    # showing state="executing" in the identity map.
    #
    # Expiring the session forces the next read to load
    # the current database value.
    #
    session.expire_all()

    return incident


def execute_claimed_restart_action(
    *,
    session: Session,
    approval_id: str,
    current_user: User,
    worker_id: str,
    settings: Settings,
) -> PendingAction:
    action = get_pending_action(
        session=session,
        approval_id=approval_id,
    )

    if action is None:
        raise ValueError(f"Approval not found: {approval_id}")

    if action.action != "restart_deployment":
        raise KubernetesRestartExecutionError("Approval is not a restart_deployment action.")

    payload = parse_restart_payload(action.payload_json)

    if action.requested_by != current_user.username:
        raise ApprovalOwnershipError("You cannot execute another user's approval.")

    # Re-authorize using CURRENT user roles.
    authorize_tool(
        tool_name="restart_deployment",
        user=current_user,
    )

    # Idempotent behavior:
    # if the action already succeeded, never restart again.
    if action.state == "succeeded":
        return action

    #
    # The worker must already have claimed this action.
    #
    _validate_claimed_action_for_execution(
        action=action,
        current_user=current_user,
        worker_id=worker_id,
        execution_error_type=(KubernetesRestartExecutionError),
    )

    #
    # Re-check the CURRENT Kubernetes write policy.
    #
    # Approval does not permanently authorize execution.
    # The policy may have changed after approval.
    #
    validate_restart_policy(
        namespace=payload.namespace,
        deployment_name=payload.name,
        write_enabled=(settings.kubernetes_write_enabled),
        allowed_namespaces_raw=(settings.kubernetes_restart_allowed_namespaces),
        allowed_deployments_raw=(settings.kubernetes_restart_allowed_deployments),
    )

    #
    # Re-read the target before performing the write.
    #
    # This is read-only.
    #
    get_deployment_state(
        name=payload.name,
        namespace=payload.namespace,
        config_mode=(settings.kubernetes_config_mode),
        context=settings.kubernetes_context,
    )

    resource_id = f"{payload.namespace}/{payload.name}"

    #
    # Record execution start.
    #
    _audit_execution_started(
        session=session,
        approval_id=approval_id,
        action_type="restart_deployment",
        actor=current_user.username,
        resource_id=resource_id,
    )

    #
    # Persist audit information before continuing.
    #
    session.commit()

    #
    # Reload the action after the transaction boundary.
    #
    executing_action = get_pending_action(
        session=session,
        approval_id=approval_id,
    )

    if executing_action is None:
        raise KubernetesRestartExecutionError("Executing action could not be reloaded.")

    #
    # The action must still be executing and still belong
    # to this worker.
    #
    if executing_action.state != "executing":
        raise KubernetesRestartExecutionError("Restart action is no longer executing.")

    if executing_action.worker_id != worker_id:
        raise KubernetesRestartExecutionError("Worker no longer owns the restart action.")

    #
    # Generate/persist the restart execution token BEFORE
    # the Kubernetes write.
    #
    # If one already exists, ensure_execution_token()
    # must reuse it.
    #
    try:
        executing_action = ensure_execution_token(
            session=session,
            approval_id=approval_id,
            expected_version=(executing_action.version),
            resource_id=resource_id,
        )

        #
        # CRITICAL:
        # Commit the token before PATCHing Kubernetes.
        #
        # This makes crash recovery safe.
        #
        session.commit()

    except Exception as exc:
        session.rollback()

        raise KubernetesRestartExecutionError("Could not persist restart execution token.") from exc

    restart_timestamp = executing_action.execution_token

    if restart_timestamp is None:
        raise KubernetesRestartExecutionError("Restart execution token is missing.")

    #
    # External Kubernetes write.
    #
    try:
        restart_deployment(
            name=payload.name,
            namespace=payload.namespace,
            restart_timestamp=restart_timestamp,
            config_mode=(settings.kubernetes_config_mode),
            context=settings.kubernetes_context,
        )

        #
        # Verify that Kubernetes actually contains the
        # exact persisted restart token.
        #
        verified = deployment_has_restart_token(
            name=payload.name,
            namespace=payload.namespace,
            restart_timestamp=restart_timestamp,
            config_mode=(settings.kubernetes_config_mode),
            context=settings.kubernetes_context,
        )

        if not verified:
            raise KubernetesRestartExecutionError("Restart patch could not be verified.")

    except KubernetesWriteError:
        #
        # A timeout/error does not necessarily mean that
        # Kubernetes failed to apply the patch.
        #
        # Reconcile against authoritative cluster state.
        #
        try:
            verified = deployment_has_restart_token(
                name=payload.name,
                namespace=payload.namespace,
                restart_timestamp=restart_timestamp,
                config_mode=(settings.kubernetes_config_mode),
                context=settings.kubernetes_context,
            )

        except KubernetesWriteError:
            verified = False

        if not verified:
            _mark_restart_failed(
                session=session,
                approval_id=approval_id,
                current_user=current_user,
                resource_id=resource_id,
                failure_reason=("restart_verification_failed"),
            )

            raise KubernetesRestartExecutionError(
                "Deployment restart failed and could not be verified."
            ) from None

    except KubernetesRestartExecutionError:
        _mark_restart_failed(
            session=session,
            approval_id=approval_id,
            current_user=current_user,
            resource_id=resource_id,
            failure_reason=("restart_verification_failed"),
        )

        raise

    #
    # At this point:
    #
    # Kubernetes restartedAt == persisted execution_token
    #
    # This proves the restart REQUEST was applied.
    # It does NOT yet prove the rollout is healthy.
    #
    _audit_restart_applied(
        session=session,
        approval_id=approval_id,
        actor=current_user.username,
        resource_id=resource_id,
        namespace=payload.namespace,
        deployment_name=payload.name,
    )

    _audit_rollout_monitor_started(
        session=session,
        approval_id=approval_id,
        actor=current_user.username,
        resource_id=resource_id,
        namespace=payload.namespace,
        deployment_name=payload.name,
    )

    #
    # Persist audit records before long polling.
    #
    # Do not leave a PostgreSQL transaction open while
    # monitoring Kubernetes.
    #
    session.commit()

    try:
        rollout_result = monitor_deployment_rollout(
            name=payload.name,
            namespace=payload.namespace,
            timeout_seconds=(settings.kubernetes_rollout_timeout_seconds),
            poll_interval_seconds=(settings.kubernetes_rollout_poll_interval_seconds),
            max_read_failures=(settings.kubernetes_rollout_max_read_failures),
            config_mode=(settings.kubernetes_config_mode),
            context=settings.kubernetes_context,
        )

    except KubernetesResourceNotFoundError as exc:
        _mark_restart_failed(
            session=session,
            approval_id=approval_id,
            current_user=current_user,
            resource_id=resource_id,
            failure_reason="deployment_disappeared",
        )

        raise KubernetesRestartExecutionError(
            "Deployment disappeared while monitoring the rollout."
        ) from exc

    result = DeploymentRestartExecutionResult(
        name=payload.name,
        namespace=payload.namespace,
        restart_applied=True,
        rollout_outcome=rollout_result.outcome,
        desired_replicas=(rollout_result.desired_replicas),
        updated_replicas=(rollout_result.updated_replicas),
        ready_replicas=(rollout_result.ready_replicas),
        available_replicas=(rollout_result.available_replicas),
    )

    result_json = result.model_dump_json()

    #
    # Rollout succeeded.
    #
    if rollout_result.outcome == "healthy":
        _audit_rollout_result(
            session=session,
            approval_id=approval_id,
            actor=current_user.username,
            resource_id=resource_id,
            namespace=payload.namespace,
            deployment_name=payload.name,
            event_type="ROLLOUT_HEALTHY",
            desired_replicas=(rollout_result.desired_replicas),
            updated_replicas=(rollout_result.updated_replicas),
            ready_replicas=(rollout_result.ready_replicas),
            available_replicas=(rollout_result.available_replicas),
        )

        current_action = get_pending_action(
            session=session,
            approval_id=approval_id,
        )

        if current_action is None:
            raise KubernetesRestartExecutionError(
                "Rollout became healthy but action could not be reloaded."
            )

        try:
            mark_action_succeeded(
                session=session,
                approval_id=approval_id,
                expected_version=(current_action.version),
                resource_id=resource_id,
                result_json=result_json,
            )

        except ConcurrentActionUpdateError as exc:
            session.rollback()

            raise KubernetesRestartExecutionError(
                "Rollout became healthy but action state could not be finalized."
            ) from exc

        _audit_execution_succeeded(
            session=session,
            approval_id=approval_id,
            action_type="restart_deployment",
            resource_id=resource_id,
            actor=current_user.username,
        )

        session.commit()

    #
    # Restart was applied, but rollout timed out.
    #
    elif rollout_result.outcome == "timeout":
        _audit_rollout_result(
            session=session,
            approval_id=approval_id,
            actor=current_user.username,
            resource_id=resource_id,
            namespace=payload.namespace,
            deployment_name=payload.name,
            event_type="ROLLOUT_TIMEOUT",
            desired_replicas=(rollout_result.desired_replicas),
            updated_replicas=(rollout_result.updated_replicas),
            ready_replicas=(rollout_result.ready_replicas),
            available_replicas=(rollout_result.available_replicas),
        )

        session.commit()

        _mark_restart_failed(
            session=session,
            approval_id=approval_id,
            current_user=current_user,
            resource_id=resource_id,
            failure_reason="rollout_timeout",
            result_json=result_json,
        )

        raise KubernetesRestartExecutionError(
            "Deployment restart was applied, but the rollout did not become healthy before timeout."
        )

    #
    # Kubernetes explicitly reported rollout failure.
    #
    else:
        _audit_rollout_result(
            session=session,
            approval_id=approval_id,
            actor=current_user.username,
            resource_id=resource_id,
            namespace=payload.namespace,
            deployment_name=payload.name,
            event_type="ROLLOUT_FAILED",
            desired_replicas=(rollout_result.desired_replicas),
            updated_replicas=(rollout_result.updated_replicas),
            ready_replicas=(rollout_result.ready_replicas),
            available_replicas=(rollout_result.available_replicas),
        )

        session.commit()

        _mark_restart_failed(
            session=session,
            approval_id=approval_id,
            current_user=current_user,
            resource_id=resource_id,
            failure_reason=("rollout_progress_deadline_exceeded"),
            result_json=result_json,
        )

        raise KubernetesRestartExecutionError(
            "Deployment restart was applied, but Kubernetes reported that the rollout failed."
        )

    final_action = get_pending_action(
        session=session,
        approval_id=approval_id,
    )

    if final_action is None:
        raise KubernetesRestartExecutionError(
            "Restart rollout completed but final action could not be loaded."
        )

    return final_action


def execute_action(
    *,
    session: Session,
    approval_id: str,
    current_user: User,
    settings: Settings,
) -> IncidentRecord | PendingAction:
    action = get_pending_action(
        session=session,
        approval_id=approval_id,
    )

    if action is None:
        raise ValueError(f"Approval not found: {approval_id}")

    if action.action == "create_incident":
        return execute_claimed_incident_action(
            session=session,
            approval_id=approval_id,
            current_user=current_user,
        )

    if action.action == "restart_deployment":
        return execute_claimed_restart_action(
            session=session,
            approval_id=approval_id,
            current_user=current_user,
            settings=settings,
        )

    raise UnsupportedActionError(f"Unsupported action: {action.action}")


def _mark_restart_failed(
    *,
    session: Session,
    approval_id: str,
    current_user: User,
    resource_id: str,
    failure_reason: str,
    result_json: str | None = None,
) -> None:
    session.rollback()

    current_action = get_pending_action(
        session=session,
        approval_id=approval_id,
    )

    if current_action is None:
        return

    if current_action.state != "executing":
        return

    try:
        mark_action_failed(
            session=session,
            approval_id=approval_id,
            expected_version=current_action.version,
            failure_reason=failure_reason,
            result_json=result_json,
        )

        _audit_execution_failed(
            session=session,
            approval_id=approval_id,
            action_type="restart_deployment",
            actor=current_user.username,
            resource_id=resource_id,
        )

        session.commit()

    except ConcurrentActionUpdateError:
        session.rollback()
