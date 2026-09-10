from sqlalchemy.orm import Session

from ai_it_support_assistant.models.incident import (
    IncidentModel,
)
from ai_it_support_assistant.schemas.incident import (
    IncidentRecord,
)


def save_incident(
    *,
    session: Session,
    incident: IncidentRecord,
) -> IncidentRecord:
    model = IncidentModel(
        incident_id=incident.incident_id,
        title=incident.title,
        description=incident.description,
        severity=incident.severity,
        service_name=incident.service_name,
        created_by=incident.created_by,
        status=incident.status,
    )

    session.add(model)
    session.flush()

    return incident


def get_incident(
    *,
    session: Session,
    incident_id: str,
) -> IncidentRecord | None:
    model = session.get(
        IncidentModel,
        incident_id,
    )

    if model is None:
        return None

    return IncidentRecord(
        incident_id=model.incident_id,
        title=model.title,
        description=model.description,
        severity=model.severity,
        service_name=model.service_name,
        created_by=model.created_by,
        status=model.status,
    )
