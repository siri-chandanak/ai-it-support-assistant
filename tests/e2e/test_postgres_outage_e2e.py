import os

import pytest
from fastapi.testclient import TestClient

from ai_it_support_assistant.models.incident import PendingActionModel
from ai_it_support_assistant.schemas.auth import User


def test_worker_does_not_execute_when_postgres_is_unavailable(
    client: TestClient,
    db_session,
    admin_auth_override: User,
) -> None:
    db_session.query(PendingActionModel).delete()
    db_session.commit()

    proposal_response = client.post(
        "/api/v1/agent/ask",
        json={
            "question": ("Restart restart-test deployment in namespace ai-support."),
        },
    )

    assert proposal_response.status_code == 200

    approval_id = proposal_response.json()["approval_id"]

    approval_response = client.post(
        "/api/v1/approvals/execute",
        json={
            "approval_id": approval_id,
            "approve": True,
        },
    )

    assert approval_response.status_code == 202
    assert approval_response.json()["state"] == "approved"


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.chaos,
]


@pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_OUTAGE_TESTS") != "true",
    reason="Requires PostgreSQL to be intentionally unavailable.",
)
def test_postgres_outage_blocks_restart_proposal(
    client: TestClient,
    admin_auth_override: User,
) -> None:
    response = client.post(
        "/api/v1/agent/ask",
        json={
            "question": ("Restart restart-test deployment in namespace ai-support."),
        },
    )

    assert response.status_code >= 500
