from sqlalchemy.orm import Session

from ai_it_support_assistant.core.config import Settings
from ai_it_support_assistant.repositories.approval_repository import (
    ConcurrentActionUpdateError,
    claim_action_for_execution,
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
from ai_it_support_assistant.services.action_payload_service import (
    parse_incident_payload,
    parse_restart_payload,
)
from ai_it_support_assistant.services.action_state_service import (
    validate_action_transition,
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
from ai_it_support_assistant.services.kubernetes_state_service import (
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


def execute_incident_action(
    *,
    session: Session,
    approval_id: str,
    current_user: User,
) -> IncidentRecord:
    action = get_pending_action(
        session=session,
        approval_id=approval_id,
    )

    if action is None:
        raise ValueError(f"Approval not found: {approval_id}")

    if action.action != "create_incident":
        raise IncidentExecutionError("Approval is not a create_incident action.")

    incident_request = parse_incident_payload(action.payload_json)

    if action.requested_by != current_user.username:
        raise ApprovalOwnershipError("You cannot execute another user's approval.")

    authorize_tool(
        tool_name="create_incident",
        user=current_user,
    )

    # Idempotent read-after-success behavior.
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

    _validate_action_for_execution(
        action=action,
        current_user=current_user,
    )

    validate_action_transition(
        current_state=action.state,
        target_state="executing",
    )

    try:
        claim_action_for_execution(
            session=session,
            approval_id=approval_id,
            expected_version=action.version,
        )

    except ConcurrentActionUpdateError:
        raise ActionCurrentlyExecutingError(
            "Another request already claimed this action."
        ) from None

    _audit_execution_started(
        session=session,
        approval_id=approval_id,
        action_type="create_incident",
        actor=current_user.username,
    )

    session.commit()

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
                expected_version=(current_action.version),
                failure_reason=("incident_creation_failed"),
            )

            _audit_execution_failed(
                session=session,
                approval_id=approval_id,
                action_type="create_incident",
                actor=current_user.username,
            )

            session.commit()

        except ConcurrentActionUpdateError:
            session.rollback()

        raise IncidentExecutionError("Incident creation failed.") from None

    session.flush()

    current_action = get_pending_action(
        session=session,
        approval_id=approval_id,
    )

    if current_action is None:
        session.rollback()

        raise IncidentExecutionError("Incident was created but approval could not be reloaded.")

    try:
        mark_action_succeeded(
            session=session,
            approval_id=approval_id,
            expected_version=current_action.version,
            resource_id=incident.incident_id,
        )

    except ConcurrentActionUpdateError as exc:
        session.rollback()

        raise IncidentExecutionError(
            "Incident was created but action state could not be finalized."
        ) from exc

    _audit_execution_succeeded(
        session=session,
        approval_id=approval_id,
        action_type="create_incident",
        resource_id=incident.incident_id,
        actor=current_user.username,
    )

    session.commit()

    return incident


def execute_restart_deployment_action(
    *,
    session: Session,
    approval_id: str,
    current_user: User,
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

    # If already succeeded, do NOT restart again.
    if action.state == "succeeded":
        return action

    _validate_action_for_execution(
        action=action,
        current_user=current_user,
    )

    #
    # IMPORTANT:
    # Re-check the current resource policy.
    #
    # An approval created yesterday must not bypass
    # today's updated allowlist.
    #
    validate_restart_policy(
        namespace=payload.namespace,
        deployment_name=payload.name,
        write_enabled=(settings.kubernetes_write_enabled),
        allowed_namespaces_raw=(settings.kubernetes_restart_allowed_namespaces),
        allowed_deployments_raw=(settings.kubernetes_restart_allowed_deployments),
    )

    #
    # Re-read the target before claiming execution.
    #
    # This is READ ONLY.
    #
    # If the Deployment disappeared, no Kubernetes
    # write should occur.
    #
    get_deployment_state(
        name=payload.name,
        namespace=payload.namespace,
        config_mode=(settings.kubernetes_config_mode),
        context=settings.kubernetes_context,
    )

    validate_action_transition(
        current_state=action.state,
        target_state="executing",
    )

    try:
        claim_action_for_execution(
            session=session,
            approval_id=approval_id,
            expected_version=action.version,
        )

    except ConcurrentActionUpdateError:
        raise ActionCurrentlyExecutingError(
            "Another request already claimed this action."
        ) from None

    resource_id = f"{payload.namespace}/{payload.name}"

    _audit_execution_started(
        session=session,
        approval_id=approval_id,
        action_type="restart_deployment",
        actor=current_user.username,
        resource_id=resource_id,
    )

    #
    # Commit the approved -> executing claim.
    #
    # This ensures another request cannot claim the
    # same action while we execute Kubernetes work.
    #
    session.commit()

    executing_action = get_pending_action(
        session=session,
        approval_id=approval_id,
    )

    if executing_action is None:
        raise KubernetesRestartExecutionError("Executing action could not be reloaded.")

    #
    # Generate/persist the restart token BEFORE
    # the Kubernetes write.
    #
    # If one already exists, ensure_execution_token()
    # reuses it.
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

        verified = deployment_has_restart_token(
            name=payload.name,
            namespace=payload.namespace,
            restart_timestamp=(restart_timestamp),
            config_mode=(settings.kubernetes_config_mode),
            context=(settings.kubernetes_context),
        )

        if not verified:
            raise KubernetesRestartExecutionError("Restart patch could not be verified.")

    except KubernetesWriteError:
        #
        # Important:
        #
        # A timeout/error does not necessarily mean
        # Kubernetes failed to apply the patch.
        #
        # Reconcile against authoritative cluster
        # state before declaring failure.
        #
        try:
            verified = deployment_has_restart_token(
                name=payload.name,
                namespace=payload.namespace,
                restart_timestamp=(restart_timestamp),
                config_mode=(settings.kubernetes_config_mode),
                context=(settings.kubernetes_context),
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
    # restartedAt == persisted execution_token
    #
    # This means the restart REQUEST was applied.
    # It does NOT yet prove all new Pods are healthy.
    #
    current_action = get_pending_action(
        session=session,
        approval_id=approval_id,
    )

    if current_action is None:
        raise KubernetesRestartExecutionError(
            "Restart was applied but action could not be reloaded."
        )

    try:
        mark_action_succeeded(
            session=session,
            approval_id=approval_id,
            expected_version=current_action.version,
            resource_id=resource_id,
        )

    except ConcurrentActionUpdateError as exc:
        session.rollback()

        raise KubernetesRestartExecutionError(
            "Restart was applied but action state could not be finalized."
        ) from exc

    _audit_execution_succeeded(
        session=session,
        approval_id=approval_id,
        action_type="restart_deployment",
        resource_id=resource_id,
        actor=current_user.username,
    )

    session.commit()

    final_action = get_pending_action(
        session=session,
        approval_id=approval_id,
    )

    if final_action is None:
        raise KubernetesRestartExecutionError(
            "Restart succeeded but final action could not be loaded."
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
        return execute_incident_action(
            session=session,
            approval_id=approval_id,
            current_user=current_user,
        )

    if action.action == "restart_deployment":
        return execute_restart_deployment_action(
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
