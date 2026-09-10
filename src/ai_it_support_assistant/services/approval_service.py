from uuid import uuid4

from sqlalchemy.orm import Session

from ai_it_support_assistant.repositories.approval_repository import (
    get_pending_action,
    mark_pending_action_approved,
    mark_pending_action_executed,
    save_pending_action,
)
from ai_it_support_assistant.schemas.approval import (
    PendingIncidentAction,
)
from ai_it_support_assistant.schemas.incident import (
    IncidentCreateRequest,
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

    if action.executed:
        raise ApprovalAlreadyExecutedError("Action was already executed.")

    mark_pending_action_approved(
        session=session,
        approval_id=approval_id,
    )

    return action.model_copy(
        update={
            "approved": True,
        }
    )


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
