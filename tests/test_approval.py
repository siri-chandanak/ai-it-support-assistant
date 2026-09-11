import pytest

from ai_it_support_assistant.repositories.approval_repository import (
    claim_action_for_execution,
    get_pending_action,
    mark_action_succeeded,
)
from ai_it_support_assistant.repositories.incident_repository import (
    get_incident,
)
from ai_it_support_assistant.schemas.incident import (
    IncidentCreateRequest,
)
from ai_it_support_assistant.services.action_state_service import (
    InvalidActionTransitionError,
)
from ai_it_support_assistant.services.approval_service import (
    ApprovalOwnershipError,
    approve_pending_action,
    create_pending_incident_action,
)


def test_pending_action_is_not_approved_or_executed(
    db_session,
) -> None:
    action = create_pending_incident_action(
        session=db_session,
        requested_by="support",
        incident=IncidentCreateRequest(
            title="VPN gateway degradation",
            description=("Authentication latency is elevated."),
            severity="high",
            service_name="vpn-gateway",
        ),
    )

    db_session.commit()

    assert action.approval_id.startswith("APR-")
    assert action.state == "pending"

    persisted = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert persisted is not None
    assert persisted.approval_id == action.approval_id
    assert persisted.requested_by == "support"
    assert persisted.state == "pending"
    assert persisted.incident_id is None


def test_other_user_cannot_approve_action(
    db_session,
) -> None:
    action = create_pending_incident_action(
        session=db_session,
        requested_by="alice",
        incident=IncidentCreateRequest(
            title="VPN gateway degradation",
            description=("Authentication latency is elevated."),
            severity="high",
        ),
    )

    db_session.commit()

    with pytest.raises(ApprovalOwnershipError):
        approve_pending_action(
            session=db_session,
            approval_id=action.approval_id,
            approved_by="bob",
        )


def test_approval_is_persisted(
    db_session,
) -> None:
    action = create_pending_incident_action(
        session=db_session,
        requested_by="alice",
        incident=IncidentCreateRequest(
            title="VPN gateway degradation",
            description=("Authentication latency is elevated."),
            severity="high",
        ),
    )

    db_session.commit()

    approved = approve_pending_action(
        session=db_session,
        approval_id=action.approval_id,
        approved_by="alice",
    )

    db_session.commit()

    assert approved.state == "approved"

    persisted = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert persisted is not None
    assert persisted.state == "approved"
    assert persisted.incident_id is None


def test_executed_action_cannot_be_approved_again(
    db_session,
) -> None:
    action = create_pending_incident_action(
        session=db_session,
        requested_by="alice",
        incident=IncidentCreateRequest(
            title="VPN gateway degradation",
            description="Authentication latency is elevated.",
            severity="high",
        ),
    )

    db_session.commit()

    approved = approve_pending_action(
        session=db_session,
        approval_id=action.approval_id,
        approved_by="alice",
    )

    db_session.commit()

    executing_version = claim_action_for_execution(
        session=db_session,
        approval_id=approved.approval_id,
        expected_version=approved.version,
    )

    mark_action_succeeded(
        session=db_session,
        approval_id=approved.approval_id,
        expected_version=executing_version,
        incident_id="INC-TEST-001",
    )

    db_session.commit()

    succeeded = get_pending_action(
        session=db_session,
        approval_id=approved.approval_id,
    )

    assert succeeded is not None
    assert succeeded.state == "succeeded"

    with pytest.raises(InvalidActionTransitionError):
        approve_pending_action(
            session=db_session,
            approval_id=approved.approval_id,
            approved_by="alice",
        )


def test_approval_execution_creates_incident(
    client,
    db_session,
    support_auth_override,
) -> None:
    action = create_pending_incident_action(
        session=db_session,
        requested_by="support",
        incident=IncidentCreateRequest(
            title="VPN gateway degradation",
            description=("Authentication latency is elevated."),
            severity="high",
            service_name="vpn-gateway",
        ),
    )

    db_session.commit()

    response = client.post(
        "/api/v1/approvals/execute",
        json={
            "approval_id": action.approval_id,
            "approve": True,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["incident_id"].startswith("INC-")
    assert body["status"] == "open"
    assert body["title"] == "VPN gateway degradation"
    assert body["severity"] == "high"

    incident = get_incident(
        session=db_session,
        incident_id=body["incident_id"],
    )

    assert incident is not None
    assert incident.incident_id == body["incident_id"]
    assert incident.title == "VPN gateway degradation"
    assert incident.status == "open"


def test_executed_approval_records_incident_id(
    client,
    db_session,
    support_auth_override,
) -> None:
    action = create_pending_incident_action(
        session=db_session,
        requested_by="support",
        incident=IncidentCreateRequest(
            title="VPN gateway degradation",
            description=("Authentication latency is elevated."),
            severity="high",
            service_name="vpn-gateway",
        ),
    )

    db_session.commit()

    response = client.post(
        "/api/v1/approvals/execute",
        json={
            "approval_id": action.approval_id,
            "approve": True,
        },
    )

    assert response.status_code == 200

    incident_id = response.json()["incident_id"]

    db_session.expire_all()

    persisted = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert persisted is not None
    assert persisted.state == "succeeded"
    assert persisted.incident_id == incident_id


def test_same_approval_cannot_create_duplicate_incident(
    client,
    db_session,
    support_auth_override,
) -> None:
    action = create_pending_incident_action(
        session=db_session,
        requested_by="support",
        incident=IncidentCreateRequest(
            title="VPN gateway degradation",
            description=("Authentication latency is elevated."),
            severity="high",
            service_name="vpn-gateway",
        ),
    )

    db_session.commit()

    first_response = client.post(
        "/api/v1/approvals/execute",
        json={
            "approval_id": action.approval_id,
            "approve": True,
        },
    )

    assert first_response.status_code == 200

    first_incident_id = first_response.json()["incident_id"]

    second_response = client.post(
        "/api/v1/approvals/execute",
        json={
            "approval_id": action.approval_id,
            "approve": True,
        },
    )

    assert second_response.status_code == 200

    second_incident_id = second_response.json()["incident_id"]

    assert second_incident_id == first_incident_id

    db_session.expire_all()

    persisted = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert persisted is not None
    assert persisted.state == "succeeded"
    assert persisted.incident_id == first_incident_id


def test_invalid_approval_returns_404(
    client,
    support_auth_override,
) -> None:
    response = client.post(
        "/api/v1/approvals/execute",
        json={
            "approval_id": "APR-NOTFOUND",
            "approve": True,
        },
    )

    assert response.status_code == 404
