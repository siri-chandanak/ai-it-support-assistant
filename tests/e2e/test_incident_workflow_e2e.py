from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.models.incident import IncidentModel, PendingActionModel
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.worker.action_worker import run_worker_once

pytestmark = pytest.mark.e2e


def test_two_workers_create_only_one_incident(
    client: TestClient,
    db_session: Session,
    support_auth_override: User,
    persisted_support_user,
) -> None:
    db_session.query(PendingActionModel).delete()
    db_session.query(IncidentModel).delete()
    db_session.commit()

    proposal_response = client.post(
        "/api/v1/agent/ask",
        json={
            "question": ("Create a high-severity incident for vpn-gateway."),
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

    settings = get_settings()

    def run_worker(worker_id: str) -> int:
        return run_worker_once(
            worker_id=worker_id,
            settings=settings,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                run_worker,
                [
                    "e2e-worker-a",
                    "e2e-worker-b",
                ],
            )
        )

    db_session.expire_all()

    action = db_session.scalar(
        select(PendingActionModel).where(PendingActionModel.approval_id == approval_id)
    )

    assert action is not None
    assert action.state == "succeeded"

    incident_count = db_session.scalar(select(func.count()).select_from(IncidentModel))

    assert incident_count == 1

    assert sum(results) == 1


def test_incident_proposal_does_not_create_incident(
    client: TestClient,
    db_session: Session,
    support_auth_override: User,
) -> None:
    before_count = db_session.scalar(select(func.count()).select_from(IncidentModel))

    question = "Create a high-severity incident for vpn-gateway."

    response = client.post(
        "/api/v1/agent/ask",
        json={
            "question": question,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["question"] == question
    assert body["action"] == "create_incident"
    assert body["approval_required"] is True
    assert body["approval_id"]
    assert body["incident_id"] is None

    db_session.expire_all()

    after_count = db_session.scalar(select(func.count()).select_from(IncidentModel))

    assert after_count == before_count


def test_incident_approval_only_queues_action(
    client: TestClient,
    db_session: Session,
    support_auth_override: User,
) -> None:
    proposal_response = client.post(
        "/api/v1/agent/ask",
        json={
            "question": ("Create a high-severity incident for vpn-gateway."),
        },
    )

    assert proposal_response.status_code == 200

    proposal_body = proposal_response.json()

    approval_id = proposal_body["approval_id"]

    before_count = db_session.scalar(select(func.count()).select_from(IncidentModel))

    approval_response = client.post(
        "/api/v1/approvals/execute",
        json={
            "approval_id": approval_id,
            "approve": True,
        },
    )

    assert approval_response.status_code == 202

    approval_body = approval_response.json()

    assert approval_body["approval_id"] == approval_id
    assert approval_body["action"] == "create_incident"
    assert approval_body["state"] == "approved"

    db_session.expire_all()

    after_count = db_session.scalar(select(func.count()).select_from(IncidentModel))

    assert after_count == before_count


def test_approved_incident_is_executed_by_worker(
    client: TestClient,
    db_session: Session,
    support_auth_override: User,
    persisted_support_user,
) -> None:
    db_session.query(PendingActionModel).delete()
    db_session.query(IncidentModel).delete()
    db_session.commit()

    proposal_response = client.post(
        "/api/v1/agent/ask",
        json={
            "question": ("Create a high-severity incident for vpn-gateway."),
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

    before_count = db_session.scalar(select(func.count()).select_from(IncidentModel))

    settings = get_settings()

    processed = run_worker_once(
        worker_id="e2e-worker-1",
        settings=settings,
    )

    assert processed == 1

    db_session.expire_all()

    action = db_session.scalar(
        select(PendingActionModel).where(PendingActionModel.approval_id == approval_id)
    )

    assert action is not None
    assert action.state == "succeeded"

    after_count = db_session.scalar(select(func.count()).select_from(IncidentModel))

    assert after_count == before_count + 1


def test_duplicate_approval_does_not_create_duplicate_incident(
    client: TestClient,
    db_session: Session,
    support_auth_override: User,
) -> None:
    db_session.query(PendingActionModel).delete()
    db_session.query(IncidentModel).delete()
    db_session.commit()

    proposal_response = client.post(
        "/api/v1/agent/ask",
        json={
            "question": ("Create a high-severity incident for vpn-gateway."),
        },
    )

    assert proposal_response.status_code == 200

    approval_id = proposal_response.json()["approval_id"]

    first_approval = client.post(
        "/api/v1/approvals/execute",
        json={
            "approval_id": approval_id,
            "approve": True,
        },
    )

    assert first_approval.status_code == 202
    assert first_approval.json()["state"] == "approved"

    settings = get_settings()

    processed = run_worker_once(
        worker_id="e2e-worker-1",
        settings=settings,
    )

    assert processed == 1

    db_session.expire_all()

    first_count = db_session.scalar(select(func.count()).select_from(IncidentModel))

    assert first_count == 1

    duplicate_approval = client.post(
        "/api/v1/approvals/execute",
        json={
            "approval_id": approval_id,
            "approve": True,
        },
    )

    assert duplicate_approval.status_code in {
        200,
        409,
    }

    run_worker_once(
        worker_id="e2e-worker-2",
        settings=settings,
    )

    db_session.expire_all()

    final_count = db_session.scalar(select(func.count()).select_from(IncidentModel))

    assert final_count == 1
