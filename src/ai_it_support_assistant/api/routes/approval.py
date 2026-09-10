from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from ai_it_support_assistant.api.dependencies.auth import (
    get_current_user,
)
from ai_it_support_assistant.db.session import (
    get_db,
)
from ai_it_support_assistant.repositories.approval_repository import (
    get_pending_action,
)
from ai_it_support_assistant.schemas.approval import (
    ApprovalExecuteRequest,
    ApprovalStatusResponse,
)
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.schemas.incident import (
    IncidentRecord,
)
from ai_it_support_assistant.services.approval_service import (
    ApprovalAlreadyExecutedError,
    ApprovalNotFoundError,
    ApprovalOwnershipError,
    approve_pending_action,
    mark_action_executed,
)
from ai_it_support_assistant.services.audit_service import (
    record_audit_event,
)
from ai_it_support_assistant.services.incident_service import (
    create_incident,
)
from ai_it_support_assistant.services.tool_authorization_service import (
    authorize_tool,
)

router = APIRouter()


@router.post(
    "/approvals/execute",
    response_model=IncidentRecord,
)
def execute_approved_action(
    request: ApprovalExecuteRequest,
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> IncidentRecord:
    if not request.approve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approval was not granted.",
        )

    try:
        action = approve_pending_action(
            session=session,
            approval_id=request.approval_id,
            approved_by=current_user.username,
        )

        record_audit_event(
            session=session,
            event_type="ACTION_APPROVED",
            actor=current_user.username,
            action_type="create_incident",
            approval_id=action.approval_id,
        )

        authorize_tool(
            tool_name="create_incident",
            user=current_user,
        )

        record_audit_event(
            session=session,
            event_type="ACTION_EXECUTION_STARTED",
            actor=current_user.username,
            action_type="create_incident",
            approval_id=action.approval_id,
        )

        idempotency_key = f"create_incident:{action.approval_id}"

        result = create_incident(
            session=session,
            request=action.incident,
            created_by=current_user.username,
            idempotency_key=idempotency_key,
        )

        mark_action_executed(
            session=session,
            action=action,
            incident_id=result.incident.incident_id,
        )

        event_type = "ACTION_EXECUTED" if result.created else "ACTION_EXECUTION_REUSED"

        record_audit_event(
            session=session,
            event_type=event_type,
            actor=current_user.username,
            action_type="create_incident",
            approval_id=action.approval_id,
            resource_id=result.incident.incident_id,
        )

        session.commit()

        return result.incident

    except ApprovalNotFoundError as exc:
        session.rollback()

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval request was not found.",
        ) from exc

    except ApprovalOwnershipError as exc:
        session.rollback()

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot approve this action.",
        ) from exc

    except ApprovalAlreadyExecutedError as exc:
        session.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Action was already executed.",
        ) from exc

    except Exception:
        session.rollback()
        raise


@router.get(
    "/approvals/{approval_id}",
    response_model=ApprovalStatusResponse,
)
def get_approval_status(
    approval_id: str,
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> ApprovalStatusResponse:
    action = get_pending_action(
        session=session,
        approval_id=approval_id,
    )

    if action is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval not found.",
        )

    if action.requested_by != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this approval.",
        )

    return ApprovalStatusResponse(
        approval_id=action.approval_id,
        action="create_incident",
        approved=action.approved,
        executed=action.executed,
        incident_id=action.incident_id,
    )
