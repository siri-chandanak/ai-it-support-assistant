from uuid import uuid4

from sqlalchemy.orm import Session

from ai_it_support_assistant.repositories.incident_repository import (
    save_incident,
)
from ai_it_support_assistant.schemas.incident import (
    IncidentCreateRequest,
    IncidentRecord,
)


class IncidentError(Exception):
    pass


def create_incident(
    *,
    session: Session,
    request: IncidentCreateRequest,
    created_by: str,
) -> IncidentRecord:
    incident = IncidentRecord(
        incident_id=f"INC-{uuid4().hex[:8].upper()}",
        title=request.title,
        description=request.description,
        severity=request.severity,
        service_name=request.service_name,
        created_by=created_by,
    )

    save_incident(
        session=session,
        incident=incident,
    )

    return incident
