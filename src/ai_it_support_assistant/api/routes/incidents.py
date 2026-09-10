from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ai_it_support_assistant.api.dependencies.auth import (
    get_current_user,
)
from ai_it_support_assistant.db.session import get_db
from ai_it_support_assistant.repositories.incident_repository import (
    get_incident_by_id,
)
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.schemas.incident import IncidentRecord

router = APIRouter(
    prefix="/incidents",
)


@router.get(
    "/{incident_id}",
    response_model=IncidentRecord,
)
def get_incident(
    incident_id: str,
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    session: Annotated[
        Session,
        Depends(get_db),
    ],
) -> IncidentRecord:
    if not {"it_support", "admin"}.intersection(current_user.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )

    incident = get_incident_by_id(
        session=session,
        incident_id=incident_id,
    )

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    return incident
