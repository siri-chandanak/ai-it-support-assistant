import json
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
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
    PendingAction,
)
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.services.approval_service import (
    ApprovalNotFoundError,
    ApprovalOwnershipError,
    approve_pending_action,
    reject_pending_action,
)

router = APIRouter()


@router.post(
    "/approvals/execute",
    response_model=ApprovalStatusResponse,
)
def execute_approved_action(
    request: ApprovalExecuteRequest,
    response: Response,
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> ApprovalStatusResponse:
    """
    Approve or reject a pending action.

    - The API does NOT execute the operational action.
    - Approving moves the action:
          pending -> approved
    - A separate worker later performs:
          approved -> executing -> succeeded/failed
    """

    try:
        action = get_pending_action(
            session=session,
            approval_id=request.approval_id,
        )

        if action is None:
            raise ApprovalNotFoundError("Approval request was not found.")

        # Only the user who requested the action may approve/reject it.
        if action.requested_by != current_user.username:
            raise ApprovalOwnershipError("You cannot approve or reject this action.")

        #
        # Reject path
        #
        if not request.approve:
            if action.state != "pending":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(f"Only pending actions can be rejected. Current state: {action.state}"),
                )

            rejected_action = reject_pending_action(
                session=session,
                approval_id=request.approval_id,
                rejected_by=current_user.username,
            )

            session.commit()

            response.status_code = status.HTTP_200_OK

            return _build_status_response(rejected_action)

        #
        # Approve path
        #
        if action.state == "pending":
            approved_action = approve_pending_action(
                session=session,
                approval_id=request.approval_id,
                approved_by=current_user.username,
            )

            session.commit()

            #
            # 202 means:
            #
            # The request was accepted,
            # but execution has NOT completed yet.
            #
            response.status_code = status.HTTP_202_ACCEPTED

            return _build_status_response(approved_action)

        #
        # Already approved.
        #
        # This is not an error.
        # The action is still waiting for / being handled
        # by the worker.
        #
        if action.state == "approved":
            response.status_code = status.HTTP_202_ACCEPTED

            return _build_status_response(action)

        #
        # The worker may already have started or
        # completed the action.
        #
        if action.state in {
            "executing",
            "succeeded",
            "failed",
            "rejected",
        }:
            response.status_code = status.HTTP_200_OK

            return _build_status_response(action)

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(f"Action cannot be processed from state: {action.state}"),
        )

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
            detail=("You cannot approve, reject, or execute this action."),
        ) from exc


def _parse_action_result(
    result_json: str | None,
) -> dict[str, object] | None:
    if result_json is None:
        return None

    try:
        result = json.loads(result_json)
    except json.JSONDecodeError:
        return None

    if not isinstance(result, dict):
        return None

    return result


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

    return _build_status_response(action)


def _build_status_response(
    action: PendingAction,
) -> ApprovalStatusResponse:
    """
    Convert the internal PendingAction domain object
    into the public API response.

    Keeping this mapping in one place prevents the POST
    and GET endpoints from drifting apart.
    """

    return ApprovalStatusResponse(
        approval_id=action.approval_id,
        action=action.action,
        state=action.state,
        resource_id=action.resource_id,
        execution_token=action.execution_token,
        failure_reason=action.failure_reason,
        result=_parse_action_result(
            action.result_json,
        ),
        created_at=action.created_at,
        approved_at=action.approved_at,
        execution_started_at=(action.execution_started_at),
        completed_at=action.completed_at,
    )


def _parse_action_result(
    result_json: str | None,
) -> dict[str, object] | None:
    """
    Safely convert stored JSON text into the dictionary
    returned by the API.
    """

    if result_json is None:
        return None

    try:
        result = json.loads(result_json)
    except json.JSONDecodeError:
        return None

    if not isinstance(result, dict):
        return None

    return result
