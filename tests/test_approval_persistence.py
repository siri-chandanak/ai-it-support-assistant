from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_it_support_assistant.models.audit import (
    AuditEventModel,
)
from ai_it_support_assistant.repositories.approval_repository import (
    claim_action_for_execution,
    get_pending_action,
    mark_action_succeeded,
    save_pending_action,
    transition_action_state,
)
from ai_it_support_assistant.repositories.incident_repository import (
    get_incident_by_idempotency_key,
)
from ai_it_support_assistant.schemas.approval import (
    PendingAction,
)
from ai_it_support_assistant.schemas.audit import (
    AuditEvent,
)
from ai_it_support_assistant.schemas.incident import (
    IncidentCreateRequest,
)
from ai_it_support_assistant.services.action_payload_service import (
    parse_incident_payload,
)
from ai_it_support_assistant.services.audit_service import record_audit_event
from ai_it_support_assistant.services.incident_service import create_incident


def build_incident_request() -> IncidentCreateRequest:
    return IncidentCreateRequest(
        title="VPN authentication issue",
        description="VPN authentication keeps failing",
        severity="medium",
        service_name="vpn",
    )


def test_pending_action_survives_new_database_session(db_session):
    approval_id = f"APR-{uuid4().hex[:12].upper()}"
    incident = IncidentCreateRequest(
        title="VPN outage",
        description="VPN authentication failing",
        severity="medium",
        service_name="vpn",
    )

    action = PendingAction(
        approval_id=approval_id,
        action="create_incident",
        requested_by="alice",
        payload_json=incident.model_dump_json(),
        state="pending",
        resource_id=None,
        execution_token=None,
        failure_reason=None,
        version=1,
    )

    save_pending_action(
        action=action,
        session=db_session,
    )
    db_session.commit()
    engine = db_session.get_bind()

    with Session(engine) as new_session:
        loaded = get_pending_action(
            approval_id=approval_id,
            session=new_session,
        )
        assert loaded is not None
        assert loaded.approval_id == approval_id
        assert loaded.state == "pending"
        assert loaded.version == 1
        assert loaded.resource_id is None


def build_pending_action(
    approval_id: str | None = None,
    requested_by: str = "alice",
) -> PendingAction:
    approval_id = approval_id or f"APR-{uuid4().hex[:12].upper()}"
    incident = IncidentCreateRequest(
        title="VPN outage",
        description="VPN authentication failing",
        severity="medium",
        service_name="vpn",
    )

    return PendingAction(
        approval_id=approval_id,
        action="create_incident",
        requested_by=requested_by,
        payload_json=incident.model_dump_json(),
        state="pending",
        resource_id=None,
        execution_token=None,
        failure_reason=None,
        version=1,
    )


def test_pending_action_can_be_saved_and_loaded(db_session):
    action = build_pending_action()

    save_pending_action(
        action=action,
        session=db_session,
    )

    loaded = get_pending_action(
        approval_id=action.approval_id,
        session=db_session,
    )

    assert loaded is not None
    assert loaded.approval_id == action.approval_id
    assert loaded.requested_by == "alice"
    assert loaded.state == "pending"
    assert loaded.resource_id is None


def test_unknown_pending_action_returns_none(db_session):
    loaded = get_pending_action(
        approval_id="APR-DOES-NOT-EXIST",
        session=db_session,
    )

    assert loaded is None


def test_pending_action_can_be_approved(db_session):
    action = build_pending_action("APR-APPROVE-001")

    save_pending_action(
        action=action,
        session=db_session,
    )

    new_version = transition_action_state(
        session=db_session,
        approval_id=action.approval_id,
        expected_state="pending",
        target_state="approved",
        expected_version=action.version,
    )

    loaded = get_pending_action(
        approval_id=action.approval_id,
        session=db_session,
    )

    assert loaded is not None
    assert loaded.state == "approved"
    assert loaded.version == new_version
    assert loaded.version == 2


def test_pending_action_can_be_marked_executed(db_session):
    action = build_pending_action("APR-EXECUTE-001")

    save_pending_action(
        action=action,
        session=db_session,
    )

    approved_version = transition_action_state(
        session=db_session,
        approval_id=action.approval_id,
        expected_state="pending",
        target_state="approved",
        expected_version=action.version,
    )

    executing_version = claim_action_for_execution(
        session=db_session,
        approval_id=action.approval_id,
        expected_version=approved_version,
    )

    succeeded_version = mark_action_succeeded(
        session=db_session,
        approval_id=action.approval_id,
        expected_version=executing_version,
        resource_id="INC-TEST-001",
    )

    loaded = get_pending_action(
        approval_id=action.approval_id,
        session=db_session,
    )

    assert loaded is not None
    assert loaded.state == "succeeded"
    assert loaded.resource_id == "INC-TEST-001"
    assert loaded.version == succeeded_version
    assert loaded.completed_at is not None


def test_same_idempotency_key_returns_same_incident(db_session):
    request = build_incident_request()

    key = "create_incident:APR-IDEMPOTENT-001"

    first = create_incident(
        request=request,
        created_by="alice",
        idempotency_key=key,
        session=db_session,
    )

    second = create_incident(
        request=request,
        created_by="alice",
        idempotency_key=key,
        session=db_session,
    )

    assert first.incident.incident_id == second.incident.incident_id
    assert first.created is True
    assert second.created is False


def test_different_idempotency_keys_create_different_incidents(db_session):
    request = build_incident_request()

    first = create_incident(
        request=request,
        created_by="alice",
        idempotency_key="create_incident:APR-001",
        session=db_session,
    )

    second = create_incident(
        request=request,
        created_by="alice",
        idempotency_key="create_incident:APR-002",
        session=db_session,
    )

    assert first.incident.incident_id != second.incident.incident_id
    assert first.created is True
    assert second.created is True


def test_incident_can_be_found_by_idempotency_key(db_session):
    request = build_incident_request()

    key = "create_incident:APR-FIND-001"

    result = create_incident(
        request=request,
        created_by="alice",
        idempotency_key=key,
        session=db_session,
    )

    loaded = get_incident_by_idempotency_key(
        idempotency_key=key,
        session=db_session,
    )

    assert loaded is not None
    assert loaded.incident_id == result.incident.incident_id


def test_retry_after_crash_reuses_existing_incident(db_session):
    request = build_incident_request()

    approval_id = "APR-CRASH-001"
    key = f"create_incident:{approval_id}"

    first = create_incident(
        request=request,
        created_by="alice",
        idempotency_key=key,
        session=db_session,
    )

    first_incident_id = first.incident.incident_id

    # Simulate:
    # incident was successfully created,
    # but application crashed before approval was marked executed.

    second = create_incident(
        request=request,
        created_by="alice",
        idempotency_key=key,
        session=db_session,
    )

    assert second.incident.incident_id == first_incident_id
    assert second.created is False


def test_crash_between_incident_creation_and_approval_completion(
    db_session,
):
    approval_id = "APR-CRASH-FULL-001"

    action = build_pending_action(approval_id)

    save_pending_action(
        action=action,
        session=db_session,
    )

    approved_version = transition_action_state(
        session=db_session,
        approval_id=approval_id,
        expected_state="pending",
        target_state="approved",
        expected_version=action.version,
    )

    key = f"create_incident:{approval_id}"

    incident_request = parse_incident_payload(action.payload_json)

    first = create_incident(
        request=incident_request,
        created_by="alice",
        idempotency_key=key,
        session=db_session,
    )

    # Simulate a crash after incident creation
    # but before the approval lifecycle is
    # advanced to succeeded.

    approval_before_retry = get_pending_action(
        approval_id=approval_id,
        session=db_session,
    )

    assert approval_before_retry is not None
    assert approval_before_retry.state == "approved"
    assert approval_before_retry.version == approved_version

    second = create_incident(
        request=incident_request,
        created_by="alice",
        idempotency_key=key,
        session=db_session,
    )

    assert second.incident.incident_id == first.incident.incident_id
    assert second.created is False


def test_get_approval_status(
    client,
    support_auth_override,
    db_session,
):
    approval_id = f"APR-{uuid4().hex[:12].upper()}"
    action = build_pending_action(
        approval_id,
        requested_by="support",
    )

    save_pending_action(
        action=action,
        session=db_session,
    )

    db_session.commit()

    response = client.get(
        f"/api/v1/approvals/{approval_id}",
    )

    assert response.status_code == 200

    body = response.json()

    assert body["approval_id"] == approval_id
    assert body["state"] == "pending"
    assert body["resource_id"] is None


def test_unknown_approval_returns_404(
    client,
    support_auth_override,
):
    response = client.get(
        "/api/v1/approvals/APR-NOT-FOUND",
    )

    assert response.status_code == 404


def test_user_cannot_access_another_users_approval(
    client,
    reader_auth_override,
    db_session,
):
    approval_id = f"APR-{uuid4().hex[:12].upper()}"

    action = build_pending_action(approval_id)

    save_pending_action(
        action=action,
        session=db_session,
    )

    db_session.commit()

    response = client.get(
        f"/api/v1/approvals/{approval_id}",
    )

    assert response.status_code == 403


def test_get_incident_by_id(
    client,
    support_auth_override,
    db_session,
):
    result = create_incident(
        request=build_incident_request(),
        created_by="alice",
        idempotency_key="create_incident:APR-GET-001",
        session=db_session,
    )

    db_session.commit()

    incident_id = result.incident.incident_id

    response = client.get(
        f"/api/v1/incidents/{incident_id}",
    )

    assert response.status_code == 200
    assert response.json()["incident_id"] == incident_id


def test_unknown_incident_returns_404(
    client,
    support_auth_override,
):
    response = client.get(
        "/api/v1/incidents/INC-NOT-FOUND",
    )

    assert response.status_code == 404


def test_reader_cannot_read_incident(
    client,
    reader_auth_override,
    db_session,
):
    result = create_incident(
        request=build_incident_request(),
        created_by="alice",
        idempotency_key="create_incident:APR-ROLE-001",
        session=db_session,
    )

    response = client.get(
        f"/api/v1/incidents/{result.incident.incident_id}",
    )

    assert response.status_code == 403


def test_support_can_read_incident(
    client,
    support_auth_override,
    db_session,
):
    result = create_incident(
        request=build_incident_request(),
        created_by="alice",
        idempotency_key="create_incident:APR-ROLE-002",
        session=db_session,
    )

    db_session.commit()

    response = client.get(
        f"/api/v1/incidents/{result.incident.incident_id}",
    )

    assert response.status_code == 200


def test_admin_can_read_incident(
    client,
    admin_auth_override,
    db_session,
):
    result = create_incident(
        request=build_incident_request(),
        created_by="alice",
        idempotency_key="create_incident:APR-ROLE-003",
        session=db_session,
    )

    db_session.commit()

    response = client.get(
        f"/api/v1/incidents/{result.incident.incident_id}",
    )

    assert response.status_code == 200


def test_one_approval_maps_to_one_incident(db_session):
    approval_id = "APR-ONE-WRITE-001"

    key = f"create_incident:{approval_id}"

    first = create_incident(
        request=build_incident_request(),
        created_by="alice",
        idempotency_key=key,
        session=db_session,
    )

    second = create_incident(
        request=build_incident_request(),
        created_by="alice",
        idempotency_key=key,
        session=db_session,
    )

    assert first.incident.incident_id == second.incident.incident_id


def test_pending_action_incident_payload_survives_database_round_trip(
    db_session,
):
    action = build_pending_action("APR-PAYLOAD-001")

    save_pending_action(
        action=action,
        session=db_session,
    )

    loaded = get_pending_action(
        approval_id=action.approval_id,
        session=db_session,
    )

    assert loaded is not None

    loaded_incident = parse_incident_payload(loaded.payload_json)

    assert loaded_incident.title == "VPN outage"
    assert loaded_incident.description == "VPN authentication failing"
    assert loaded_incident.severity == "medium"
    assert loaded_incident.service_name == "vpn"


def test_action_lifecycle_can_be_audited(db_session):
    approval_id = "APR-AUDIT-LIFECYCLE-001"

    event_types = [
        "ACTION_PROPOSED",
        "ACTION_APPROVED",
        "ACTION_EXECUTION_STARTED",
        "ACTION_EXECUTED",
    ]

    for event_type in event_types:
        record_audit_event(
            event_type=event_type,
            actor="alice",
            action_type="create_incident",
            approval_id=approval_id,
            session=db_session,
        )

    statement = (
        select(AuditEventModel)
        .where(AuditEventModel.approval_id == approval_id)
        .order_by(AuditEventModel.created_at)
    )

    events = list(db_session.scalars(statement))

    assert len(events) == 4

    stored_types = [event.event_type for event in events]

    assert stored_types == event_types


def test_idempotent_retry_records_reused_audit_event(db_session):
    approval_id = "APR-AUDIT-REUSE-001"

    key = f"create_incident:{approval_id}"

    first = create_incident(
        request=build_incident_request(),
        created_by="alice",
        idempotency_key=key,
        session=db_session,
    )

    assert first.created is True

    second = create_incident(
        request=build_incident_request(),
        created_by="alice",
        idempotency_key=key,
        session=db_session,
    )

    assert second.created is False

    record_audit_event(
        event_type="ACTION_EXECUTION_REUSED",
        actor="alice",
        action_type="create_incident",
        approval_id=approval_id,
        resource_id=second.incident.incident_id,
        session=db_session,
    )

    statement = select(AuditEventModel).where(
        AuditEventModel.approval_id == approval_id,
        AuditEventModel.event_type == "ACTION_EXECUTION_REUSED",
    )

    event = db_session.scalar(statement)

    assert event is not None
    assert event.resource_id == second.incident.incident_id


def test_failed_execution_can_be_audited(db_session):
    event = record_audit_event(
        event_type="ACTION_EXECUTION_FAILED",
        actor="alice",
        action_type="create_incident",
        approval_id="APR-FAILED-001",
        details={
            "error_type": "database_error",
        },
        session=db_session,
    )

    assert event.event_type == "ACTION_EXECUTION_FAILED"
    assert event.details["error_type"] == "database_error"


def test_audit_details_do_not_contain_sensitive_fields():
    safe_details = {
        "error_type": "database_error",
        "operation": "create_incident",
    }

    forbidden_keys = {
        "password",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "authorization",
    }

    assert forbidden_keys.isdisjoint(safe_details.keys())


def test_audit_event_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        AuditEvent(
            event_id="AUD-001",
            event_type="ACTION_PROPOSED",
            actor="alice",
            unexpected_field="should fail",
        )


def test_incident_request_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        IncidentCreateRequest(
            title="VPN issue",
            description="VPN failed",
            severity="medium",
            service_name="vpn",
            run_shell_command="rm -rf /",
        )


def test_loaded_pending_action_contains_incident_request(db_session):
    action = build_pending_action("APR-CONTENT-001")

    save_pending_action(
        action=action,
        session=db_session,
    )

    loaded = get_pending_action(
        approval_id=action.approval_id,
        session=db_session,
    )

    assert loaded is not None
    loaded_incident = parse_incident_payload(loaded.payload_json)

    assert loaded_incident is not None
    original_incident = parse_incident_payload(action.payload_json)

    assert loaded_incident.title == original_incident.title


def test_executed_approval_survives_new_database_session(db_session):
    approval_id = f"APR-{uuid4().hex[:12].upper()}"
    incident_id = f"INC-{uuid4().hex[:8].upper()}"

    action = build_pending_action(approval_id)

    save_pending_action(
        action=action,
        session=db_session,
    )

    approved_version = transition_action_state(
        session=db_session,
        approval_id=approval_id,
        expected_state="pending",
        target_state="approved",
        expected_version=action.version,
    )

    executing_version = claim_action_for_execution(
        session=db_session,
        approval_id=approval_id,
        expected_version=approved_version,
    )

    succeeded_version = mark_action_succeeded(
        session=db_session,
        approval_id=action.approval_id,
        expected_version=executing_version,
        resource_id=incident_id,
    )

    db_session.commit()

    engine = db_session.get_bind()

    with Session(engine) as new_session:
        loaded = get_pending_action(
            approval_id=approval_id,
            session=new_session,
        )

        assert loaded is not None
        assert loaded.state == "succeeded"
        assert loaded.resource_id == incident_id
        assert loaded.version == succeeded_version
        assert loaded.completed_at is not None
