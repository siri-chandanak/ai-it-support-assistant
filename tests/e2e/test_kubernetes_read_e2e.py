from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from ai_it_support_assistant.schemas.auth import User

pytestmark = pytest.mark.e2e


def test_it_support_can_read_kubernetes_deployment_state(
    client: TestClient,
    support_auth_override: User,
    persisted_support_user,
) -> None:
    question = "How many ready replicas does restart-test in namespace ai-support have?"

    response = client.post(
        "/api/v1/agent/ask",
        json={
            "question": question,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["question"] == question
    assert body["action"] == "kubernetes_state"
    assert body["answer"]


def test_reader_cannot_read_kubernetes_deployment_state(
    client: TestClient,
    reader_auth_override: User,
) -> None:
    question = "How many ready replicas does restart-test in namespace ai-support have?"

    with patch(
        "ai_it_support_assistant.services.agent_service.get_kubernetes_resource_state"
    ) as mock_kubernetes_tool:
        response = client.post(
            "/api/v1/agent/ask",
            json={
                "question": question,
            },
        )

    assert response.status_code == 403
    mock_kubernetes_tool.assert_not_called()
