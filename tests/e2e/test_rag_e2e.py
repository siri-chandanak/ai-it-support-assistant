import pytest
from fastapi.testclient import TestClient

from ai_it_support_assistant.schemas.auth import User

pytestmark = pytest.mark.e2e


def test_authenticated_reader_can_reach_agent_rag_path(
    client: TestClient,
    reader_auth_override: User,
) -> None:
    response = client.post(
        "/api/v1/agent/ask",
        json={
            "question": "How do I troubleshoot the VPN?",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["question"] == "How do I troubleshoot the VPN?"
    assert body["action"] == "rag"
    assert body["answer"]


def test_rag_abstains_when_context_is_insufficient(
    client: TestClient,
    reader_auth_override: User,
) -> None:
    question = "What is the CEO's home Wi-Fi password?"

    response = client.post(
        "/api/v1/agent/ask",
        json={
            "question": question,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["question"] == question
    assert body["action"] == "rag"

    assert body["answer"]
    assert "couldn't find sufficiently relevant information" in body["answer"].lower()
