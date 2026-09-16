from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ai_it_support_assistant.api.dependencies.auth import (
    get_current_user,
)
from ai_it_support_assistant.db.session import (
    get_db,
)
from ai_it_support_assistant.repositories.service_status_repository import (
    get_service_status,
)
from ai_it_support_assistant.services.policy_authorization_service import (
    authorize_service_status_read,
    build_policy_subject,
)
from ai_it_support_assistant.services.policy_enforcement_service import (
    AuthorizationDeniedError,
    enforce_policy,
)
from ai_it_support_assistant.services.policy_service import (
    PolicyEvaluationError,
)

router = APIRouter()


@router.get("/services/{service_name}/status")
def read_service_status(
    service_name: str,
    current_user=Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        subject = build_policy_subject(current_user)

        decision = authorize_service_status_read(
            subject=subject,
            service_name=service_name,
            session=session,
        )

        enforce_policy(decision)

    except AuthorizationDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to perform this action.",
        ) from exc

    except PolicyEvaluationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authorization service is temporarily unavailable.",
        ) from exc

    return get_service_status(service_name)
