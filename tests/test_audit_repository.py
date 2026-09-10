from uuid import uuid4

from sqlalchemy import select

from ai_it_support_assistant.models.audit import AuditEventModel
from ai_it_support_assistant.repositories.audit_repository import save_audit_event
from ai_it_support_assistant.schemas.audit import AuditEvent
from ai_it_support_assistant.services.audit_service import record_audit_event


def test_audit_event_details_default_to_empty_dict():
    event = AuditEvent(
        event_id="AUD-001",
        event_type="ACTION_PROPOSED",
        actor="alice",
    )

    assert event.details == {}


def test_audit_event_is_persisted(db_session):
    event = AuditEvent(
        event_id=f"AUD-{uuid4().hex[:12].upper()}",
        event_type="ACTION_PROPOSED",
        actor="alice",
        action_type="create_incident",
        approval_id="APR-AUDIT-001",
        resource_id=None,
        details={},
    )

    save_audit_event(
        event=event,
        session=db_session,
    )

    statement = select(AuditEventModel).where(AuditEventModel.event_id == event.event_id)

    stored = db_session.scalar(statement)

    assert stored is not None
    assert stored.event_type == "ACTION_PROPOSED"
    assert stored.actor == "alice"
    assert stored.approval_id == "APR-AUDIT-001"


def test_record_audit_event_creates_database_record(db_session):
    event = record_audit_event(
        event_type="ACTION_APPROVED",
        actor="alice",
        action_type="create_incident",
        approval_id="APR-AUDIT-002",
        resource_id=None,
        details={"source": "approval_endpoint"},
        session=db_session,
    )

    statement = select(AuditEventModel).where(AuditEventModel.event_id == event.event_id)

    stored = db_session.scalar(statement)

    assert stored is not None
    assert stored.event_type == "ACTION_APPROVED"
    assert stored.actor == "alice"


def test_audit_event_details_are_not_shared():
    first = AuditEvent(
        event_id="AUD-001",
        event_type="ACTION_PROPOSED",
        actor="alice",
    )

    second = AuditEvent(
        event_id="AUD-002",
        event_type="ACTION_PROPOSED",
        actor="bob",
    )

    first.details["key"] = "value"

    assert second.details == {}
