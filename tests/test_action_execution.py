from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from ai_it_support_assistant.repositories.approval_repository import (
    ConcurrentActionUpdateError,
    claim_action_for_execution,
    get_pending_action,
)
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.schemas.incident import (
    IncidentCreateRequest,
    IncidentRecord,
)
from ai_it_support_assistant.services.action_execution_service import (
    ActionCurrentlyExecutingError,
    ActionFailedError,
    ActionNotApprovedError,
    ActionRejectedError,
    IncidentExecutionError,
    execute_incident_action,
)
from ai_it_support_assistant.services.action_state_service import (
    InvalidActionTransitionError,
)
from ai_it_support_assistant.services.approval_service import (
    approve_pending_action,
    create_pending_incident_action,
    reject_pending_action,
)


@pytest.fixture
def current_user() -> User:
    return User(
        user_id=UUID("00000000-0000-0000-0000-000000000020"),
        username="support",
        roles=["it_support"],
        disabled=False,
    )


@pytest.fixture
def incident_request() -> IncidentCreateRequest:
    return IncidentCreateRequest(
        title="VPN authentication failure",
        description=(
            "User cannot authenticate to the corporate VPN after completing normal troubleshooting."
        ),
        severity="medium",
        service_name="vpn",
    )


@pytest.fixture
def pending_action(
    db_session,
    incident_request: IncidentCreateRequest,
):
    action = create_pending_incident_action(
        session=db_session,
        requested_by="support",
        incident=incident_request,
    )

    db_session.commit()

    return action


@pytest.fixture
def approved_action(
    db_session,
    pending_action,
):
    approved = approve_pending_action(
        session=db_session,
        approval_id=pending_action.approval_id,
        approved_by="support",
    )

    db_session.commit()

    return approved


def test_only_one_worker_can_claim_execution(
    db_session,
    approved_action,
) -> None:
    approval_id = approved_action.approval_id
    original_version = approved_action.version

    new_version = claim_action_for_execution(
        session=db_session,
        approval_id=approval_id,
        expected_version=original_version,
    )

    db_session.commit()

    assert new_version == original_version + 1

    updated = get_pending_action(
        session=db_session,
        approval_id=approval_id,
    )

    assert updated is not None
    assert updated.state == "executing"
    assert updated.version == original_version + 1
    assert updated.execution_started_at is not None

    with pytest.raises(ConcurrentActionUpdateError):
        claim_action_for_execution(
            session=db_session,
            approval_id=approval_id,
            expected_version=original_version,
        )

    db_session.rollback()


def test_pending_action_cannot_execute(
    db_session,
    pending_action,
    current_user: User,
) -> None:
    with pytest.raises(ActionNotApprovedError):
        execute_incident_action(
            session=db_session,
            approval_id=pending_action.approval_id,
            current_user=current_user,
        )


def test_rejected_action_cannot_execute(
    monkeypatch: pytest.MonkeyPatch,
    db_session,
    pending_action,
    current_user: User,
) -> None:
    create_incident_calls = 0

    def fake_create_incident(**kwargs):
        nonlocal create_incident_calls
        create_incident_calls += 1

        raise AssertionError("create_incident must not run for rejected action")

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.action_execution_service.create_incident"),
        fake_create_incident,
    )

    rejected = reject_pending_action(
        session=db_session,
        approval_id=pending_action.approval_id,
        rejected_by=current_user.username,
    )

    db_session.commit()

    assert rejected.state == "rejected"

    with pytest.raises(ActionRejectedError):
        execute_incident_action(
            session=db_session,
            approval_id=pending_action.approval_id,
            current_user=current_user,
        )

    assert create_incident_calls == 0


def test_executing_action_cannot_be_claimed_again(
    db_session,
    approved_action,
    current_user: User,
) -> None:
    claim_action_for_execution(
        session=db_session,
        approval_id=approved_action.approval_id,
        expected_version=approved_action.version,
    )

    db_session.commit()

    with pytest.raises(ActionCurrentlyExecutingError):
        execute_incident_action(
            session=db_session,
            approval_id=approved_action.approval_id,
            current_user=current_user,
        )


def test_successful_incident_execution(
    monkeypatch: pytest.MonkeyPatch,
    db_session,
    approved_action,
    current_user: User,
) -> None:
    expected_incident_id = f"INC-{uuid4().hex[:8].upper()}"

    def fake_create_incident(
        *,
        session,
        request,
        created_by,
        idempotency_key,
    ) -> IncidentRecord:
        assert request == approved_action.incident
        assert created_by == current_user.username

        assert idempotency_key == (f"create_incident:{approved_action.approval_id}")

        assert session is db_session

        incident = IncidentRecord(
            incident_id=expected_incident_id,
            title=request.title,
            description=request.description,
            severity=request.severity,
            service_name=request.service_name,
            created_by=created_by,
            status="open",
            created_at=datetime.now(UTC),
        )
        return SimpleNamespace(
            incident=incident,
        )

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.action_execution_service.create_incident"),
        fake_create_incident,
    )

    result = execute_incident_action(
        session=db_session,
        approval_id=approved_action.approval_id,
        current_user=current_user,
    )

    assert result.incident_id == expected_incident_id

    updated = get_pending_action(
        session=db_session,
        approval_id=approved_action.approval_id,
    )

    assert updated is not None
    assert updated.state == "succeeded"
    assert updated.incident_id == expected_incident_id
    assert updated.failure_reason is None
    assert updated.execution_started_at is not None
    assert updated.completed_at is not None


def test_external_failure_marks_action_failed(
    monkeypatch: pytest.MonkeyPatch,
    db_session,
    approved_action,
    current_user: User,
) -> None:
    def fake_create_incident(**kwargs):
        raise RuntimeError("simulated external incident provider failure")

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.action_execution_service.create_incident"),
        fake_create_incident,
    )

    with pytest.raises(IncidentExecutionError):
        execute_incident_action(
            session=db_session,
            approval_id=approved_action.approval_id,
            current_user=current_user,
        )

    updated = get_pending_action(
        session=db_session,
        approval_id=approved_action.approval_id,
    )

    assert updated is not None
    assert updated.state == "failed"
    assert updated.failure_reason == "incident_creation_failed"
    assert updated.execution_started_at is not None
    assert updated.completed_at is not None


def test_failed_action_does_not_automatically_retry(
    monkeypatch: pytest.MonkeyPatch,
    db_session,
    approved_action,
    current_user: User,
) -> None:
    create_incident_calls = 0

    def failing_create_incident(**kwargs):
        nonlocal create_incident_calls
        create_incident_calls += 1

        raise RuntimeError("simulated provider failure")

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.action_execution_service.create_incident"),
        failing_create_incident,
    )

    with pytest.raises(IncidentExecutionError):
        execute_incident_action(
            session=db_session,
            approval_id=approved_action.approval_id,
            current_user=current_user,
        )

    assert create_incident_calls == 1

    with pytest.raises(ActionFailedError):
        execute_incident_action(
            session=db_session,
            approval_id=approved_action.approval_id,
            current_user=current_user,
        )

    assert create_incident_calls == 1


def test_retry_after_success_does_not_create_second_incident(
    monkeypatch: pytest.MonkeyPatch,
    db_session,
    approved_action,
    current_user: User,
) -> None:
    create_incident_calls = 0

    expected_incident_id = f"INC-{uuid4().hex[:8].upper()}"

    fake_incident = IncidentRecord(
        incident_id=expected_incident_id,
        title=approved_action.incident.title,
        description=approved_action.incident.description,
        severity=approved_action.incident.severity,
        service_name=approved_action.incident.service_name,
        created_by=current_user.username,
        status="open",
        created_at=datetime.now(UTC),
    )

    def fake_create_incident(**kwargs):
        nonlocal create_incident_calls

        create_incident_calls += 1

        return SimpleNamespace(
            incident=fake_incident,
        )

    def fake_get_incident(
        *,
        session,
        incident_id: str,
    ) -> IncidentRecord | None:
        assert session is db_session
        assert incident_id == expected_incident_id

        return fake_incident

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.action_execution_service.create_incident"),
        fake_create_incident,
    )

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.action_execution_service.get_incident"),
        fake_get_incident,
    )

    first = execute_incident_action(
        session=db_session,
        approval_id=approved_action.approval_id,
        current_user=current_user,
    )

    second = execute_incident_action(
        session=db_session,
        approval_id=approved_action.approval_id,
        current_user=current_user,
    )

    assert first.incident_id == expected_incident_id
    assert second.incident_id == expected_incident_id

    assert create_incident_calls == 1


def test_approval_changes_pending_to_approved(
    db_session,
    pending_action,
    current_user: User,
) -> None:
    assert pending_action.state == "pending"

    approved = approve_pending_action(
        session=db_session,
        approval_id=pending_action.approval_id,
        approved_by=current_user.username,
    )

    db_session.commit()

    assert approved.state == "approved"
    assert approved.version == pending_action.version + 1


def test_rejection_changes_pending_to_rejected(
    db_session,
    pending_action,
    current_user: User,
) -> None:
    assert pending_action.state == "pending"

    rejected = reject_pending_action(
        session=db_session,
        approval_id=pending_action.approval_id,
        rejected_by=current_user.username,
    )

    db_session.commit()

    assert rejected.state == "rejected"
    assert rejected.version == pending_action.version + 1


def test_rejected_action_is_terminal(
    db_session,
    pending_action,
    current_user: User,
) -> None:
    rejected = reject_pending_action(
        session=db_session,
        approval_id=pending_action.approval_id,
        rejected_by=current_user.username,
    )

    db_session.commit()

    assert rejected.state == "rejected"

    with pytest.raises(InvalidActionTransitionError):
        approve_pending_action(
            session=db_session,
            approval_id=pending_action.approval_id,
            approved_by=current_user.username,
        )
