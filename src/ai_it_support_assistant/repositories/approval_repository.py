from sqlalchemy.orm import Session

from ai_it_support_assistant.models.incident import (
    PendingIncidentActionModel,
)
from ai_it_support_assistant.schemas.approval import (
    PendingIncidentAction,
)
from ai_it_support_assistant.schemas.incident import (
    IncidentCreateRequest,
)


def save_pending_action(
    *,
    session: Session,
    action: PendingIncidentAction,
) -> None:
    model = PendingIncidentActionModel(
        approval_id=action.approval_id,
        requested_by=action.requested_by,
        incident_title=action.incident.title,
        incident_description=action.incident.description,
        incident_severity=action.incident.severity,
        service_name=action.incident.service_name,
        approved=action.approved,
        executed=action.executed,
    )

    session.add(model)
    session.flush()


def get_pending_action(
    *,
    session: Session,
    approval_id: str,
) -> PendingIncidentAction | None:
    model = session.get(
        PendingIncidentActionModel,
        approval_id,
    )

    if model is None:
        return None

    return PendingIncidentAction(
        approval_id=model.approval_id,
        requested_by=model.requested_by,
        incident=IncidentCreateRequest(
            title=model.incident_title,
            description=model.incident_description,
            severity=model.incident_severity,
            service_name=model.service_name,
        ),
        approved=model.approved,
        executed=model.executed,
    )


def update_pending_action(
    *,
    session: Session,
    action: PendingIncidentAction,
) -> None:
    model = session.get(
        PendingIncidentActionModel,
        action.approval_id,
    )

    if model is None:
        return

    model.approved = action.approved
    model.executed = action.executed

    session.flush()
