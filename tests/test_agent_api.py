from unittest.mock import patch
from uuid import UUID

from fastapi.testclient import TestClient

from ai_it_support_assistant.api.dependencies.auth import (
    get_current_user,
)
from ai_it_support_assistant.main import app
from ai_it_support_assistant.schemas.agent import AgentResponse
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.schemas.policy import (
    PolicyDecision,
)
from ai_it_support_assistant.services.agent_router_service import (
    AgentRoutingError,
)
from ai_it_support_assistant.services.live_status_service import (
    ServiceNotFoundError,
)
from ai_it_support_assistant.services.policy_enforcement_service import (
    AuthorizationDeniedError,
)
from ai_it_support_assistant.services.policy_service import (
    PolicyEvaluationError,
)

client = TestClient(app)


def _auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
    }


def _override_it_support_user() -> User:
    return User(
        user_id=UUID("11111111-1111-1111-1111-111111111111"),
        username="support",
        roles=["it_support"],
    )


def _override_reader_user() -> User:
    return User(
        user_id=UUID("22222222-2222-2222-2222-222222222222"),
        username="reader",
        roles=["reader"],
    )


def test_agent_endpoint_requires_authentication() -> None:
    response = client.post(
        "/api/v1/agent/ask",
        json={"question": "What does the VPN runbook recommend?"},
    )

    assert response.status_code == 401


def test_agent_endpoint_returns_agent_response() -> None:
    app.dependency_overrides[get_current_user] = _override_it_support_user

    mocked_response = AgentResponse(
        question="Is vpn-gateway healthy right now?",
        action="live_status",
        answer=("vpn-gateway is degraded. Authentication latency is elevated."),
    )

    try:
        with patch(
            "ai_it_support_assistant.api.routes.agent.handle_agent_request",
            return_value=mocked_response,
        ):
            response = client.post(
                "/api/v1/agent/ask",
                json={"question": ("Is vpn-gateway healthy right now?")},
            )

        assert response.status_code == 200
        assert response.json()["action"] == "live_status"

    finally:
        app.dependency_overrides.clear()


def test_agent_maps_authorization_denied_error_to_403() -> None:
    app.dependency_overrides[get_current_user] = _override_reader_user

    decision = PolicyDecision(
        allowed=False,
        reason_code="missing_permission",
        reason="Not authorized.",
        policy_id="global-permission-v1",
        obligations=[],
    )

    try:
        with patch(
            "ai_it_support_assistant.api.routes.agent.handle_agent_request",
            side_effect=AuthorizationDeniedError(decision),
        ):
            response = client.post(
                "/api/v1/agent/ask",
                json={
                    "question": "Is vpn-gateway healthy right now?"
                },
            )

        assert response.status_code == 403

    finally:
        app.dependency_overrides.clear()

def test_agent_maps_unknown_service_to_404() -> None:
    app.dependency_overrides[get_current_user] = _override_it_support_user

    try:
        with patch(
            "ai_it_support_assistant.api.routes.agent.handle_agent_request",
            side_effect=ServiceNotFoundError("Service was not found."),
        ):
            response = client.post(
                "/api/v1/agent/ask",
                json={"question": ("Is unicorn-payment-engine healthy right now?")},
            )

        assert response.status_code == 404

    finally:
        app.dependency_overrides.clear()


def test_agent_maps_routing_failure_to_502() -> None:
    app.dependency_overrides[get_current_user] = _override_it_support_user

    try:
        with patch(
            "ai_it_support_assistant.api.routes.agent.handle_agent_request",
            side_effect=AgentRoutingError("Routing failed."),
        ):
            response = client.post(
                "/api/v1/agent/ask",
                json={"question": "Some ambiguous request"},
            )

        assert response.status_code == 502

    finally:
        app.dependency_overrides.clear()


def test_agent_rejects_empty_question() -> None:
    app.dependency_overrides[get_current_user] = _override_reader_user

    try:
        response = client.post(
            "/api/v1/agent/ask",
            json={"question": ""},
        )

        assert response.status_code == 422

    finally:
        app.dependency_overrides.clear()

def test_agent_maps_policy_evaluation_error_to_503() -> None:
    app.dependency_overrides[get_current_user] = _override_reader_user

    try:
        with patch(
            "ai_it_support_assistant.api.routes.agent.handle_agent_request",
            side_effect=PolicyEvaluationError(
                "Policy evaluation failed."
            ),
        ):
            response = client.post(
                "/api/v1/agent/ask",
                json={
                    "question": "Is vpn-gateway healthy right now?"
                },
            )

        assert response.status_code == 503

    finally:
        app.dependency_overrides.clear()