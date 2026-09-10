import pytest

from ai_it_support_assistant.repositories.approval_repository import (
    get_pending_action,
)
from ai_it_support_assistant.repositories.incident_repository import (
    get_incident,
)
from ai_it_support_assistant.schemas.incident import (
    IncidentCreateRequest,
)
from ai_it_support_assistant.services.approval_service import (
    ApprovalAlreadyExecutedError,
    ApprovalOwnershipError,
    approve_pending_action,
    create_pending_incident_action,
    mark_action_executed,
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
    assert action.approved is False
    assert action.executed is False

    persisted = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert persisted is not None
    assert persisted.approval_id == action.approval_id
    assert persisted.requested_by == "support"
    assert persisted.approved is False
    assert persisted.executed is False
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

    assert approved.approved is True

    persisted = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert persisted is not None
    assert persisted.approved is True
    assert persisted.executed is False
    assert persisted.incident_id is None


def test_executed_action_cannot_be_approved_again(
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

    executed = mark_action_executed(
        session=db_session,
        action=approved,
        incident_id="INC-TEST-001",
    )

    db_session.commit()

    assert executed.executed is True
    assert executed.incident_id == "INC-TEST-001"

    db_session.expire_all()

    persisted = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert persisted is not None
    assert persisted.executed is True
    assert persisted.incident_id == "INC-TEST-001"

    with pytest.raises(ApprovalAlreadyExecutedError):
        approve_pending_action(
            session=db_session,
            approval_id=action.approval_id,
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
    assert persisted.approved is True
    assert persisted.executed is True
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

    # Your current API design blocks already-executed
    # approvals instead of silently executing again.
    assert second_response.status_code == 409

    db_session.expire_all()

    persisted = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert persisted is not None
    assert persisted.executed is True
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
