import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ai_it_support_assistant.models.audit import (
    AuditEventModel,
)
from ai_it_support_assistant.schemas.audit import (
    AuditEvent,
)


def save_audit_event(
    *,
    session: Session,
    event: AuditEvent,
) -> None:
    model = AuditEventModel(
        event_id=event.event_id,
        event_type=event.event_type,
        actor=event.actor,
        action_type=event.action_type,
        approval_id=event.approval_id,
        resource_id=event.resource_id,
        details_json=json.dumps(
            event.details,
        ),
        created_at=datetime.now(UTC),
    )

    session.add(model)
    session.flush()
