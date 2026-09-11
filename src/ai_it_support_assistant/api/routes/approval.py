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
from ai_it_support_assistant.services.action_execution_service import (
    ActionCurrentlyExecutingError,
    ActionFailedError,
    ActionNotApprovedError,
    ActionRejectedError,
    IncidentExecutionError,
    execute_incident_action,
)
from ai_it_support_assistant.services.approval_service import (
    ApprovalNotFoundError,
    ApprovalOwnershipError,
    approve_pending_action,
    reject_pending_action,
)

router = APIRouter()


@router.post(
    "/approvals/execute",
    response_model=IncidentRecord | ApprovalStatusResponse,
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
) -> IncidentRecord | ApprovalStatusResponse:
    try:
        if not request.approve:
            rejected_action = reject_pending_action(
                session=session,
                approval_id=request.approval_id,
                rejected_by=current_user.username,
            )

            return ApprovalStatusResponse(
                approval_id=rejected_action.approval_id,
                action=rejected_action.action,
                state=rejected_action.state,
                incident_id=rejected_action.incident_id,
                failure_reason=rejected_action.failure_reason,
            )

        action = get_pending_action(
            session=session,
            approval_id=request.approval_id,
        )

        if action is None:
            raise ApprovalNotFoundError("Approval request was not found.")

        if action.state == "succeeded":
            return execute_incident_action(
                session=session,
                approval_id=request.approval_id,
                current_user=current_user,
            )

        if action.state == "pending":
            approve_pending_action(
                session=session,
                approval_id=request.approval_id,
                approved_by=current_user.username,
            )

        return execute_incident_action(
            session=session,
            approval_id=request.approval_id,
            current_user=current_user,
        )

    except ApprovalNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval request was not found.",
        ) from exc

    except ApprovalOwnershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot approve or execute this action.",
        ) from exc

    except (
        ActionNotApprovedError,
        ActionRejectedError,
        ActionCurrentlyExecutingError,
        ActionFailedError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except IncidentExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc


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
        action=action.action,
        state=action.state,
        incident_id=action.incident_id,
        failure_reason=action.failure_reason,
    )
