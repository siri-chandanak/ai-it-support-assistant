from uuid import uuid4

from sqlalchemy.orm import Session

from ai_it_support_assistant.repositories.approval_repository import (
    get_pending_action,
    mark_pending_action_executed,
    save_pending_action,
    transition_action_state,
)
from ai_it_support_assistant.schemas.approval import (
    PendingIncidentAction,
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


def create_pending_incident_action(
    *,
    session: Session,
    requested_by: str,
    incident: IncidentCreateRequest,
) -> PendingIncidentAction:
    action = PendingIncidentAction(
        approval_id=(f"APR-{uuid4().hex[:8].upper()}"),
        requested_by=requested_by,
        incident=incident,
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
) -> PendingIncidentAction:
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


def mark_action_executed(
    *,
    session: Session,
    action: PendingIncidentAction,
    incident_id: str,
) -> PendingIncidentAction:
    if not action.approved:
        raise ApprovalError("Action has not been approved.")

    if action.executed:
        raise ApprovalAlreadyExecutedError("Action was already executed.")

    mark_pending_action_executed(
        session=session,
        approval_id=action.approval_id,
        incident_id=incident_id,
    )

    return action.model_copy(
        update={
            "executed": True,
            "incident_id": incident_id,
        }
    )


def reject_pending_action(
    *,
    session: Session,
    approval_id: str,
    rejected_by: str,
) -> PendingIncidentAction:
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
