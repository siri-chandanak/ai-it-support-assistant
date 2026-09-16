from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from ai_it_support_assistant.schemas.policy import (
    PolicyRequest,
    PolicyResource,
    PolicySubject,
)
from ai_it_support_assistant.services.policy_service import (
    PolicyEvaluationError,
    evaluate_policy,
)


def build_subject(
    *,
    permissions: list[str],
    disabled: bool = False,
) -> PolicySubject:
    return PolicySubject(
        subject_id="alice",
        username="alice",
        roles=["it_support"],
        permissions=permissions,
        disabled=disabled,
    )


def test_service_status_allowed(
    client,
    support_auth_override,
) -> None:
    with patch(
        "ai_it_support_assistant.api.routes.service_status.get_service_status",
        return_value={
            "status": "healthy",
        },
    ):
        response = client.get("/api/v1/services/payment-api/status")

    assert response.status_code == 200


def test_service_status_denied_without_permission(
    client,
    reader_auth_override,
) -> None:
    response = client.get("/api/v1/services/payment-api/status")

    assert response.status_code == 403

    assert response.json() == {"detail": ("You are not authorized to perform this action.")}


def test_denied_service_status_does_not_execute(
    client,
    reader_auth_override,
) -> None:
    with patch(
        "ai_it_support_assistant.api.routes.service_status.get_service_status"
    ) as mock_get_status:
        response = client.get("/api/v1/services/payment-api/status")

    assert response.status_code == 403

    mock_get_status.assert_not_called()


def test_service_status_policy_failure_returns_503(
    client,
    support_auth_override,
) -> None:
    with patch(
        "ai_it_support_assistant.api.routes.service_status.authorize_service_status_read",
        side_effect=PolicyEvaluationError("Database unavailable."),
    ):
        response = client.get("/api/v1/services/payment-api/status")

    assert response.status_code == 503

    assert response.json() == {"detail": ("Authorization service is temporarily unavailable.")}


def test_reader_cannot_read_service_status() -> None:
    session = MagicMock(spec=Session)

    request = PolicyRequest(
        subject=build_subject(
            permissions=[],
        ),
        action="service_status.read",
        resource=PolicyResource(
            resource_type="service",
            resource_id="payment-api",
        ),
    )

    decision = evaluate_policy(
        request=request,
        session=session,
    )

    assert decision.allowed is False
    assert decision.reason_code == "missing_permission"


def test_it_support_can_read_service_status() -> None:
    session = MagicMock(spec=Session)

    request = PolicyRequest(
        subject=build_subject(
            permissions=["service-status:read"],
        ),
        action="service_status.read",
        resource=PolicyResource(
            resource_type="service",
            resource_id="payment-api",
        ),
    )

    decision = evaluate_policy(
        request=request,
        session=session,
    )

    assert decision.allowed is True


def test_admin_can_read_service_status() -> None:
    session = MagicMock(spec=Session)

    request = PolicyRequest(
        subject=build_subject(
            permissions=["service-status:read"],
        ),
        action="service_status.read",
        resource=PolicyResource(
            resource_type="service",
            resource_id="payment-api",
        ),
    )

    decision = evaluate_policy(
        request=request,
        session=session,
    )

    assert decision.allowed is True
