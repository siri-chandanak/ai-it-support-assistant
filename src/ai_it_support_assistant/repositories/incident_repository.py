from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_it_support_assistant.models.incident import (
    IncidentModel,
)
from ai_it_support_assistant.schemas.incident import (
    IncidentRecord,
)


def _to_incident_record(
    model: IncidentModel,
) -> IncidentRecord:
    return IncidentRecord(
        incident_id=model.incident_id,
        title=model.title,
        description=model.description,
        severity=model.severity,
        service_name=model.service_name,
        created_by=model.created_by,
        status=model.status,
        created_at=model.created_at,
    )


def save_incident(
    *,
    session: Session,
    incident: IncidentRecord,
    idempotency_key: str,
) -> IncidentRecord:
    model = IncidentModel(
        incident_id=incident.incident_id,
        idempotency_key=idempotency_key,
        title=incident.title,
        description=incident.description,
        severity=incident.severity,
        service_name=incident.service_name,
        created_by=incident.created_by,
        status=incident.status,
        created_at=incident.created_at,
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

    return _to_incident_record(model)


def get_incident_by_idempotency_key(
    *,
    session: Session,
    idempotency_key: str,
) -> IncidentRecord | None:
    statement = select(IncidentModel).where(IncidentModel.idempotency_key == idempotency_key)

    model = session.scalar(statement)

    if model is None:
        return None

    return _to_incident_record(model)


def get_incident_by_id(
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

    return _to_incident_record(model)
