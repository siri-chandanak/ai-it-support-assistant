from uuid import uuid4

from sqlalchemy.orm import Session

from ai_it_support_assistant.repositories.audit_repository import (
    save_audit_event,
)
from ai_it_support_assistant.schemas.audit import (
    AuditEvent,
)


def record_audit_event(
    *,
    session: Session,
    event_type: str,
    actor: str,
    action_type: str | None = None,
    approval_id: str | None = None,
    resource_id: str | None = None,
    details: dict[str, str] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        event_id=f"AUD-{uuid4().hex[:12].upper()}",
        event_type=event_type,
        actor=actor,
        action_type=action_type,
        approval_id=approval_id,
        resource_id=resource_id,
        details=details or {},
    )

    save_audit_event(
        session=session,
        event=event,
    )

    return event
