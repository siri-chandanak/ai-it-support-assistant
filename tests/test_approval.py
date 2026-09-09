import pytest

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
    )

    db_session.commit()

    assert executed.executed is True

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
