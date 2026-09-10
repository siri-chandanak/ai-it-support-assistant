from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_it_support_assistant.repositories.incident_repository import (
    get_incident_by_idempotency_key,
    save_incident,
)
from ai_it_support_assistant.schemas.incident import (
    IncidentCreateRequest,
    IncidentExecutionResult,
    IncidentRecord,
)


class IncidentError(Exception):
    pass


def create_incident(
    *,
    session: Session,
    request: IncidentCreateRequest,
    created_by: str,
    idempotency_key: str,
) -> IncidentExecutionResult:
    existing_incident = get_incident_by_idempotency_key(
        session=session,
        idempotency_key=idempotency_key,
    )

    if existing_incident is not None:
        return IncidentExecutionResult(
            incident=existing_incident,
            created=False,
        )

    incident = IncidentRecord(
        incident_id=f"INC-{uuid4().hex[:8].upper()}",
        title=request.title,
        description=request.description,
        severity=request.severity,
        service_name=request.service_name,
        created_by=created_by,
        status="open",
        created_at=datetime.now(UTC),
    )

    try:
        save_incident(
            session=session,
            incident=incident,
            idempotency_key=idempotency_key,
        )

    except IntegrityError as exc:
        session.rollback()

        existing_incident = get_incident_by_idempotency_key(
            session=session,
            idempotency_key=idempotency_key,
        )

        if existing_incident is None:
            raise IncidentError("Failed to create incident.") from exc

        return IncidentExecutionResult(
            incident=existing_incident,
            created=False,
        )

    return IncidentExecutionResult(
        incident=incident,
        created=True,
    )
