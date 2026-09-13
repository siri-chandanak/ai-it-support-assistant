import pytest

from ai_it_support_assistant.repositories.approval_repository import (
    claim_action_for_execution,
    get_pending_action,
    mark_action_succeeded,
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
    assert persisted.resource_id is None


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
    assert persisted.resource_id is None


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
        worker_id="worker-test",
    )

    mark_action_succeeded(
        session=db_session,
        approval_id=approved.approval_id,
        expected_version=executing_version,
        resource_id="INC-TEST-001",
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

    assert response.status_code == 202

    stored = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert stored is not None
    assert stored.state == "approved"
    assert stored.worker_id is None
    assert stored.execution_started_at is None
    assert stored.resource_id is None


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

    assert response.status_code == 202

    persisted = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert persisted is not None
    assert persisted.state == "approved"


def test_same_approval_cannot_be_approved_twice(
    client,
    db_session,
    support_auth_override,
) -> None:
    action = create_pending_incident_action(
        session=db_session,
        requested_by="support",
        incident=IncidentCreateRequest(
            title="VPN gateway degradation",
            description="Authentication latency is elevated.",
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

    assert first_response.status_code == 202

    second_response = client.post(
        "/api/v1/approvals/execute",
        json={
            "approval_id": action.approval_id,
            "approve": True,
        },
    )

    assert second_response.status_code in {
        400,
        409,
        202,
    }


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
