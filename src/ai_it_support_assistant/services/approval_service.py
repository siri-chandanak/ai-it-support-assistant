from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from ai_it_support_assistant.repositories.approval_repository import (
    get_pending_action,
    save_pending_action,
    set_action_execution_token,
    transition_action_state,
)
from ai_it_support_assistant.schemas.approval import (
    ActionType,
    PendingAction,
)
from ai_it_support_assistant.schemas.incident import (
    IncidentCreateRequest,
)
from ai_it_support_assistant.services.action_state_service import (
    validate_action_transition,
)


class ApprovalError(Exception):
    pass


class ApprovalNotFoundError(ApprovalError):
    pass


class ApprovalOwnershipError(ApprovalError):
    pass


class ApprovalAlreadyExecutedError(ApprovalError):
    pass


class ActionExecutionTokenError(Exception):
    pass


def create_pending_incident_action(
    *,
    session: Session,
    requested_by: str,
    incident: IncidentCreateRequest,
) -> PendingAction:
    return create_pending_action(
        session=session,
        requested_by=requested_by,
        action_type="create_incident",
        payload_json=incident.model_dump_json(),
    )


def create_pending_action(
    *,
    session: Session,
    requested_by: str,
    action_type: ActionType,
    payload_json: str,
) -> PendingAction:
    action = PendingAction(
        approval_id=(f"APR-{uuid4().hex[:8].upper()}"),
        action=action_type,
        requested_by=requested_by,
        payload_json=payload_json,
        state="pending",
        version=1,
        resource_id=None,
        execution_token=None,
        failure_reason=None,
    )

    save_pending_action(
        session=session,
        action=action,
    )

    return action


def approve_pending_action(
    *,
    session: Session,
    approval_id: str,
    approved_by: str,
) -> PendingAction:
    action = get_pending_action(
        session=session,
        approval_id=approval_id,
    )

    if action is None:
        raise ApprovalNotFoundError("Approval request was not found.")

    if action.requested_by != approved_by:
        raise ApprovalOwnershipError("Approval belongs to another user.")

    validate_action_transition(
        current_state=action.state,
        target_state="approved",
    )

    transition_action_state(
        session=session,
        approval_id=approval_id,
        expected_state="pending",
        target_state="approved",
        expected_version=action.version,
    )

    updated_action = get_pending_action(
        session=session,
        approval_id=approval_id,
    )

    if updated_action is None:
        raise ApprovalNotFoundError("Approval request disappeared after update.")

    return updated_action


def reject_pending_action(
    *,
    session: Session,
    approval_id: str,
    rejected_by: str,
) -> PendingAction:
    action = get_pending_action(
        session=session,
        approval_id=approval_id,
    )

    if action is None:
        raise ApprovalNotFoundError(f"Approval not found: {approval_id}")

    if action.requested_by != rejected_by:
        raise ApprovalOwnershipError("Only the user who requested the action can reject it.")

    validate_action_transition(
        current_state=action.state,
        target_state="rejected",
    )

    transition_action_state(
        session=session,
        approval_id=approval_id,
        expected_state="pending",
        target_state="rejected",
        expected_version=action.version,
    )

    session.flush()

    updated_action = get_pending_action(
        session=session,
        approval_id=approval_id,
    )

    if updated_action is None:
        raise ApprovalNotFoundError(f"Approval disappeared after rejection: {approval_id}")

    return updated_action


def ensure_execution_token(
    *,
    session: Session,
    approval_id: str,
    expected_version: int,
    resource_id: str,
) -> PendingAction:
    action = get_pending_action(
        session=session,
        approval_id=approval_id,
    )

    if action is None:
        raise ActionExecutionTokenError("Action was not found.")

    if action.state != "executing":
        raise ActionExecutionTokenError("Action is not executing.")

    # Important for retries:
    # if a token already exists, always reuse it.
    if action.execution_token is not None:
        return action

    execution_token = datetime.now(UTC).isoformat()

    updated_rows = set_action_execution_token(
        session=session,
        approval_id=approval_id,
        expected_version=expected_version,
        execution_token=execution_token,
        resource_id=resource_id,
    )

    if updated_rows != 1:
        # Another worker may have written the token
        # between our read and update.
        refreshed_action = get_pending_action(
            session=session,
            approval_id=approval_id,
        )

        if refreshed_action is not None and refreshed_action.execution_token is not None:
            return refreshed_action

        raise ActionExecutionTokenError("Failed to persist execution token.")

    session.flush()

    updated_action = get_pending_action(
        session=session,
        approval_id=approval_id,
    )

    if updated_action is None:
        raise ActionExecutionTokenError("Action disappeared after execution token update.")

    if updated_action.execution_token is None:
        raise ActionExecutionTokenError("Execution token was not persisted.")

    return updated_action
