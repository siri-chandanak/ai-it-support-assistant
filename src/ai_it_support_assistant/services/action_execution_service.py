from sqlalchemy.orm import Session

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
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.schemas.incident import IncidentRecord
from ai_it_support_assistant.services.action_state_service import (
    validate_action_transition,
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


class ApprovalOwnershipError(Exception):
    pass


class ActionNotApprovedError(Exception):
    pass


class ActionRejectedError(Exception):
    pass


class ActionCurrentlyExecutingError(Exception):
    pass


class ActionFailedError(Exception):
    pass


class IncidentExecutionError(Exception):
    pass


def _audit_execution_started(
    *,
    session: Session,
    approval_id: str,
    actor: str,
) -> None:
    record_audit_event(
        session=session,
        event_type="ACTION_EXECUTION_STARTED",
        actor=actor,
        action_type="create_incident",
        approval_id=approval_id,
        resource_id=None,
        details={
            "previous_state": "approved",
            "new_state": "executing",
        },
    )


def _audit_execution_succeeded(
    *,
    session: Session,
    approval_id: str,
    incident_id: str,
    actor: str,
) -> None:
    record_audit_event(
        session=session,
        event_type="ACTION_EXECUTED",
        actor=actor,
        action_type="create_incident",
        approval_id=approval_id,
        resource_id=incident_id,
        details={
            "previous_state": "executing",
            "new_state": "succeeded",
        },
    )


def _audit_execution_failed(
    *,
    session: Session,
    approval_id: str,
    actor: str,
) -> None:
    record_audit_event(
        session=session,
        event_type="ACTION_EXECUTION_FAILED",
        actor=actor,
        action_type="create_incident",
        approval_id=approval_id,
        resource_id=None,
        details={
            "previous_state": "executing",
            "new_state": "failed",
        },
    )


def execute_incident_action(
    *,
    session: Session,
    approval_id: str,
    current_user: User,
) -> IncidentRecord:
    # Load action
    action = get_pending_action(
        session=session,
        approval_id=approval_id,
    )

    if action is None:
        raise ValueError(f"Approval not found: {approval_id}")

    # Ownership check
    if action.requested_by != current_user.username:
        raise ApprovalOwnershipError("You cannot execute another user's approval.")

    # Re-authorize at execution time
    authorize_tool(
        tool_name="create_incident",
        user=current_user,
    )

    # Already succeeded
    if action.state == "succeeded":
        if action.incident_id is None:
            raise IncidentExecutionError("Succeeded action is missing incident ID.")

        incident = get_incident(
            session=session,
            incident_id=action.incident_id,
        )
        if incident is None:
            raise IncidentExecutionError("Existing incident could not be found.")

        return incident

    # Pending cannot execute
    if action.state == "pending":
        raise ActionNotApprovedError("Action has not been approved.")

    # Rejected cannot execute
    if action.state == "rejected":
        raise ActionRejectedError("Action was rejected.")

    # Another worker already owns execution
    if action.state == "executing":
        raise ActionCurrentlyExecutingError("Action is already being executed.")

    # No automatic retry yet
    if action.state == "failed":
        raise ActionFailedError("Action previously failed and cannot be retried automatically.")

    # Defensive guard
    if action.state != "approved":
        raise ActionNotApprovedError(f"Action cannot execute from state: {action.state}")

    # Validate approved -> executing
    validate_action_transition(
        current_state=action.state,
        target_state="executing",
    )

    try:
        _executing_version = claim_action_for_execution(
            session=session,
            approval_id=approval_id,
            expected_version=action.version,
        )

    except ConcurrentActionUpdateError:
        # Another request/worker won the race.
        raise ActionCurrentlyExecutingError(
            "Another request already claimed this action."
        ) from None

    _audit_execution_started(
        session=session,
        approval_id=approval_id,
        actor=current_user.username,
    )

    session.commit()

    # Stable idempotency identity
    idempotency_key = f"create_incident:{approval_id}"

    # Perform external write
    try:
        execution_result = create_incident(
            session=session,
            request=action.incident,
            created_by=current_user.username,
            idempotency_key=idempotency_key,
        )
        incident = execution_result.incident

    except Exception:
        session.rollback()
        # Do not save the raw exception in PostgreSQL.
        safe_failure_reason = "incident_creation_failed"
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
                failure_reason=safe_failure_reason,
            )

            _audit_execution_failed(
                session=session,
                approval_id=approval_id,
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
            incident_id=incident.incident_id,
        )

    except ConcurrentActionUpdateError as exc:
        session.rollback()
        raise IncidentExecutionError(
            "Incident was created but action state could not be finalized."
        ) from exc

    _audit_execution_succeeded(
        session=session,
        approval_id=approval_id,
        incident_id=incident.incident_id,
        actor=current_user.username,
    )

    session.commit()

    return incident
