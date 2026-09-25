import pytest
from fastapi.testclient import TestClient

from ai_it_support_assistant.schemas.auth import User

pytestmark = pytest.mark.e2e


def test_it_support_can_get_current_service_status(
    client: TestClient,
    support_auth_override: User,
) -> None:
    question = "What is the current status of vpn-gateway?"

    response = client.post(
        "/api/v1/agent/ask",
        json={
            "question": question,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["question"] == question
    assert body["action"] == "live_status"
    assert body["answer"]


def test_agent_distinguishes_procedure_from_current_status(
    client: TestClient,
    support_auth_override: User,
) -> None:
    troubleshooting_response = client.post(
        "/api/v1/agent/ask",
        json={
            "question": "How do I troubleshoot vpn-gateway?",
        },
    )

    assert troubleshooting_response.status_code == 200

    troubleshooting_body = troubleshooting_response.json()

    assert troubleshooting_body["action"] == "rag"
    assert troubleshooting_body["answer"]

    status_response = client.post(
        "/api/v1/agent/ask",
        json={
            "question": "What is vpn-gateway status right now?",
        },
    )

    assert status_response.status_code == 200

    status_body = status_response.json()

    assert status_body["action"] == "live_status"
    assert status_body["answer"]
