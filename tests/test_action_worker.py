import json
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from ai_it_support_assistant.core.config import Settings
from ai_it_support_assistant.db.session import SessionLocal
from ai_it_support_assistant.models.incident import (
    PendingActionModel,
)
from ai_it_support_assistant.repositories.approval_repository import (
    ConcurrentActionUpdateError,
    claim_action_for_execution,
    get_pending_action,
    mark_pending_action_approved,
    reclaim_stale_action,
    save_pending_action,
)
from ai_it_support_assistant.schemas.approval import PendingAction
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.schemas.policy import (
    PolicyDecision,
)
from ai_it_support_assistant.worker.action_worker import (
    parse_restart_action,
    reconcile_stale_incident_action,
    reconcile_stale_restart_action,
    run_worker_once,
)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        action_worker_enabled=True,
        action_worker_poll_interval_seconds=0.01,
        action_worker_batch_size=5,
        action_worker_stale_after_seconds=300,
        kubernetes_write_enabled=True,
        kubernetes_restart_allowed_namespaces="dev",
        kubernetes_restart_allowed_deployments="ai-support-api",
        kubernetes_config_mode="kubeconfig",
        kubernetes_context="test-context",
    )


@pytest.fixture(autouse=True)
def clean_pending_actions(db_session):
    db_session.query(PendingActionModel).delete()
    db_session.commit()

    yield

    db_session.query(PendingActionModel).delete()
    db_session.commit()


def build_pending_incident_action(
    *,
    approval_id: str | None = None,
    requested_by: str = "admin",
) -> PendingAction:
    return PendingAction(
        approval_id=(approval_id or f"APR-TEST-{uuid4().hex[:8].upper()}"),
        requested_by=requested_by,
        action="create_incident",
        payload_json=(
            '{"title":"VPN outage",'
            '"description":"VPN unavailable",'
            '"severity":"high",'
            '"service_name":"vpn"}'
        ),
        state="pending",
        version=1,
        resource_id=None,
        execution_token=None,
        worker_id=None,
        last_heartbeat_at=None,
        requested_roles_json="[]",
        result_json=None,
        created_at=datetime.now(UTC),
        approved_at=None,
        execution_started_at=None,
        completed_at=None,
        failure_reason=None,
    )


def allowed_restart_reconciliation_decision() -> PolicyDecision:
    return PolicyDecision(
        allowed=True,
        reason_code="allowed",
        reason="Restart reconciliation allowed.",
        policy_id="deployment-restart-v1",
        obligations=[
            "audit_execution",
            "verify_rollout",
        ],
    )


def test_approval_only_transitions_to_approved(
    db_session,
) -> None:
    action = build_pending_incident_action()

    save_pending_action(
        session=db_session,
        action=action,
    )
    db_session.commit()

    approved = mark_pending_action_approved(
        session=db_session,
        approval_id=action.approval_id,
    )

    db_session.commit()

    assert approved is True

    stored = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert stored is not None
    assert stored.state == "approved"
    assert stored.execution_started_at is None
    assert stored.worker_id is None


def test_approval_endpoint_does_not_execute_tool(
    client,
    db_session,
    support_auth_override,
) -> None:
    action = build_pending_incident_action(
        requested_by="support",
    )

    save_pending_action(
        session=db_session,
        action=action,
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
    assert response.json()["state"] == "approved"

    stored = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert stored is not None
    assert stored.state == "approved"
    assert stored.execution_started_at is None
    assert stored.worker_id is None


def test_worker_can_claim_approved_action(
    db_session,
) -> None:
    action = build_pending_incident_action()

    save_pending_action(
        session=db_session,
        action=action,
    )

    db_session.flush()

    mark_pending_action_approved(
        session=db_session,
        approval_id=action.approval_id,
    )

    db_session.commit()

    approved_action = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert approved_action is not None
    assert approved_action.state == "approved"

    new_version = claim_action_for_execution(
        session=db_session,
        approval_id=approved_action.approval_id,
        expected_version=approved_action.version,
        worker_id="worker-A",
    )

    db_session.commit()

    claimed = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert claimed is not None
    assert claimed.state == "executing"
    assert claimed.worker_id == "worker-A"
    assert claimed.execution_started_at is not None
    assert claimed.last_heartbeat_at is not None
    assert claimed.version == new_version


def test_only_one_worker_can_claim_action(
    db_session,
) -> None:
    action = build_pending_incident_action()

    save_pending_action(
        session=db_session,
        action=action,
    )

    mark_pending_action_approved(
        session=db_session,
        approval_id=action.approval_id,
    )

    db_session.commit()

    approved = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert approved is not None

    version = approved.version

    claim_action_for_execution(
        session=db_session,
        approval_id=approved.approval_id,
        expected_version=version,
        worker_id="worker-A",
    )

    db_session.commit()

    with pytest.raises(ConcurrentActionUpdateError):
        claim_action_for_execution(
            session=db_session,
            approval_id=approved.approval_id,
            expected_version=version,
            worker_id="worker-B",
        )


@patch("ai_it_support_assistant.worker.action_worker.execute_claimed_action")
def test_run_worker_once_executes_approved_action(
    mock_execute_claimed_action,
    db_session,
    settings: Settings,
) -> None:
    action = build_pending_incident_action()

    save_pending_action(
        session=db_session,
        action=action,
    )

    mark_pending_action_approved(
        session=db_session,
        approval_id=action.approval_id,
    )

    db_session.commit()

    settings.action_worker_batch_size = 1

    processed = run_worker_once(
        worker_id="worker-A",
        settings=settings,
    )

    assert processed == 1
    assert mock_execute_claimed_action.call_count == 1


@patch("ai_it_support_assistant.worker.action_worker.execute_claimed_action")
def test_worker_respects_batch_size(
    mock_execute_claimed_action: Mock,
    db_session,
    settings,
) -> None:
    approval_ids = [f"APR-BATCH-{uuid4().hex[:8].upper()}" for _ in range(3)]

    for approval_id in approval_ids:
        action = build_pending_incident_action(
            approval_id=approval_id,
        )

        save_pending_action(
            session=db_session,
            action=action,
        )

        db_session.flush()

        approved = mark_pending_action_approved(
            session=db_session,
            approval_id=approval_id,
        )

        assert approved is True

    db_session.commit()

    settings.action_worker_batch_size = 1

    processed = run_worker_once(
        worker_id="worker-A",
        settings=settings,
    )

    assert processed == 1
    assert mock_execute_claimed_action.call_count == 1

    states = {}
    for approval_id in approval_ids:
        action = get_pending_action(
            session=db_session,
            approval_id=approval_id,
        )

        assert action is not None
        states[approval_id] = action.state

    approved_count = sum(state == "approved" for state in states.values())

    executing_count = sum(state == "executing" for state in states.values())
    assert approved_count == 2
    assert executing_count == 1


def test_healthy_execution_cannot_be_reclaimed(
    db_session,
) -> None:
    approval_id = f"APR-STALE-{uuid4().hex[:8].upper()}"

    action = build_pending_incident_action(
        approval_id=approval_id,
    )

    save_pending_action(
        session=db_session,
        action=action,
    )

    db_session.flush()

    approved = mark_pending_action_approved(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert approved is True

    db_session.commit()

    current = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert current is not None
    assert current.state == "approved"

    claimed_version = claim_action_for_execution(
        session=db_session,
        approval_id=current.approval_id,
        expected_version=current.version,
        worker_id="worker-old",
    )

    db_session.commit()

    executing = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert executing is not None
    assert executing.state == "executing"
    assert executing.worker_id == "worker-old"
    assert executing.version == claimed_version
    assert executing.last_heartbeat_at is not None

    stale_before = datetime.now(UTC) - timedelta(minutes=5)

    with pytest.raises(ConcurrentActionUpdateError):
        reclaim_stale_action(
            session=db_session,
            approval_id=executing.approval_id,
            expected_version=executing.version,
            stale_before=stale_before,
            worker_id="worker-new",
        )

    db_session.rollback()

    unchanged = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert unchanged is not None
    assert unchanged.state == "executing"
    assert unchanged.worker_id == "worker-old"


def test_stale_execution_can_be_reclaimed(
    db_session,
) -> None:
    approval_id = f"APR-STALE-{uuid4().hex[:8].upper()}"

    action = build_pending_incident_action(
        approval_id=approval_id,
    )

    save_pending_action(
        session=db_session,
        action=action,
    )

    db_session.flush()

    approved = mark_pending_action_approved(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert approved is True

    db_session.commit()

    approved_action = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert approved_action is not None

    claim_action_for_execution(
        session=db_session,
        approval_id=approved_action.approval_id,
        expected_version=approved_action.version,
        worker_id="worker-old",
    )

    db_session.commit()

    model = db_session.get(
        PendingActionModel,
        action.approval_id,
    )

    assert model is not None

    model.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=10)

    db_session.commit()

    current = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert current is not None
    assert current.state == "executing"
    assert current.worker_id == "worker-old"

    stale_before = datetime.now(UTC) - timedelta(minutes=5)

    new_version = reclaim_stale_action(
        session=db_session,
        approval_id=current.approval_id,
        expected_version=current.version,
        stale_before=stale_before,
        worker_id="worker-new",
    )

    db_session.commit()

    reclaimed = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert reclaimed is not None

    assert reclaimed.state == "executing"

    assert reclaimed.worker_id == "worker-new"

    assert reclaimed.version == new_version

    assert reclaimed.last_heartbeat_at is not None


def test_only_one_worker_can_reclaim_stale_action(
    db_session,
) -> None:
    approval_id = f"APR-STALE-{uuid4().hex[:8].upper()}"

    action = build_pending_incident_action(
        approval_id=approval_id,
    )

    save_pending_action(
        session=db_session,
        action=action,
    )

    db_session.flush()

    approved = mark_pending_action_approved(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert approved is True

    db_session.commit()

    approved_action = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert approved_action is not None

    claim_action_for_execution(
        session=db_session,
        approval_id=approved_action.approval_id,
        expected_version=approved_action.version,
        worker_id="worker-old",
    )

    db_session.commit()

    model = db_session.get(
        PendingActionModel,
        action.approval_id,
    )

    assert model is not None

    model.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=10)

    db_session.commit()

    stale_action = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert stale_action is not None

    stale_before = datetime.now(UTC) - timedelta(minutes=5)

    original_version = stale_action.version

    # Worker A wins.
    reclaim_stale_action(
        session=db_session,
        approval_id=stale_action.approval_id,
        expected_version=original_version,
        stale_before=stale_before,
        worker_id="worker-A",
    )

    db_session.commit()

    # Worker B uses the same old version.
    with pytest.raises(ConcurrentActionUpdateError):
        reclaim_stale_action(
            session=db_session,
            approval_id=stale_action.approval_id,
            expected_version=original_version,
            stale_before=stale_before,
            worker_id="worker-B",
        )

    db_session.rollback()

    final_action = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert final_action is not None

    assert final_action.state == "executing"
    assert final_action.worker_id == "worker-A"


@patch("ai_it_support_assistant.worker.action_worker.authorize_incident_create")
@patch("ai_it_support_assistant.worker.action_worker.load_and_authorize_action_user")
@patch("ai_it_support_assistant.worker.action_worker.create_incident")
@patch("ai_it_support_assistant.worker.action_worker.get_incident_by_idempotency_key")
def test_stale_incident_reuses_existing_incident(
    mock_get_incident: Mock,
    mock_create_incident: Mock,
    mock_load_user: Mock,
    mock_authorize_incident_create: Mock,
    db_session,
    settings,
) -> None:
    approval_id = f"APR-STALE-{uuid4().hex[:8].upper()}"

    action = build_pending_incident_action(
        approval_id=approval_id,
    )

    save_pending_action(
        session=db_session,
        action=action,
    )

    mark_pending_action_approved(
        session=db_session,
        approval_id=action.approval_id,
    )

    db_session.commit()

    approved_action = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert approved_action is not None

    claim_action_for_execution(
        session=db_session,
        approval_id=approved_action.approval_id,
        expected_version=approved_action.version,
        worker_id="worker-old",
    )

    db_session.commit()

    stale_action = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert stale_action is not None

    current_user = User(
        user_id=uuid4(),
        username=action.requested_by,
        roles=["admin"],
        disabled=False,
    )

    mock_load_user.return_value = current_user

    mock_authorize_incident_create.return_value = PolicyDecision(
        allowed=True,
        reason_code="allowed",
        reason=("Incident reconciliation allowed."),
        policy_id="incident-create-v1",
        obligations=[
            "audit_execution",
        ],
    )

    mock_get_incident.return_value = "INC-EXISTING-1"

    reconcile_stale_incident_action(
        action=stale_action,
        worker_id="worker-new",
        settings=settings,
    )

    mock_create_incident.assert_not_called()

    mock_get_incident.assert_called_once_with(
        session=(mock_get_incident.call_args.kwargs["session"]),
        idempotency_key=(f"create_incident:{action.approval_id}"),
    )

    mock_authorize_incident_create.assert_called_once()

    call_kwargs = mock_authorize_incident_create.call_args.kwargs

    assert call_kwargs["phase"] == "reconciliation"

    assert call_kwargs["approval_state"] is None

    assert call_kwargs["subject"].username == action.requested_by

    with SessionLocal() as verification_session:
        stored = get_pending_action(
            session=verification_session,
            approval_id=action.approval_id,
        )

        assert stored is not None

        assert stored.state == "succeeded"

        assert stored.resource_id == "INC-EXISTING-1"


@patch("ai_it_support_assistant.worker.action_worker.load_and_authorize_action_user")
@patch("ai_it_support_assistant.worker.action_worker.authorize_deployment_restart")
@patch("ai_it_support_assistant.worker.action_worker.monitor_deployment_rollout")
@patch("ai_it_support_assistant.worker.action_worker.restart_deployment")
@patch("ai_it_support_assistant.worker.action_worker.get_deployment_restart_token")
def test_restart_recovery_does_not_repatch(
    mock_get_token: Mock,
    mock_restart: Mock,
    mock_monitor: Mock,
    mock_authorize_deployment_restart: Mock,
    mock_load_user: Mock,
    db_session,
    settings,
) -> None:
    action = PendingAction(
        approval_id=(f"APR-RESTART-RECOVERY-{uuid4().hex[:8].upper()}"),
        action="restart_deployment",
        requested_by="admin",
        requested_roles_json='["admin"]',
        payload_json=(
            '{"name":"ai-support-api",'
            '"namespace":"dev",'
            '"evidence_desired_replicas":3,'
            '"evidence_ready_replicas":1,'
            '"evidence_available_replicas":1,'
            '"warnings":[]}'
        ),
        state="executing",
        version=3,
        resource_id="dev/ai-support-api",
        execution_token="T1",
    )

    save_pending_action(
        session=db_session,
        action=action,
    )

    db_session.commit()

    stored_action = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert stored_action is not None

    current_user = User(
        user_id=uuid4(),
        username="admin",
        roles=["admin"],
        disabled=False,
    )

    mock_load_user.return_value = current_user

    mock_authorize_deployment_restart.return_value = PolicyDecision(
        allowed=True,
        reason_code="allowed",
        reason=("Deployment restart reconciliation allowed."),
        policy_id="deployment-restart-v1",
        obligations=[
            "audit_execution",
            "verify_rollout",
        ],
    )

    # Kubernetes already contains the persisted token.
    #
    # Therefore reconciliation must NOT patch again.
    mock_get_token.return_value = "T1"

    rollout_result = Mock()
    rollout_result.outcome = "healthy"

    rollout_result.model_dump_json.return_value = '{"outcome":"healthy"}'

    mock_monitor.return_value = rollout_result

    reconcile_stale_restart_action(
        action=stored_action,
        worker_id="worker-new",
        settings=settings,
    )

    mock_load_user.assert_called_once()

    mock_authorize_deployment_restart.assert_called_once()

    policy_kwargs = mock_authorize_deployment_restart.call_args.kwargs

    assert policy_kwargs["phase"] == "reconciliation"

    assert policy_kwargs["approval_state"] is None

    assert policy_kwargs["namespace"] == "dev"

    assert policy_kwargs["deployment_name"] == "ai-support-api"

    assert policy_kwargs["writes_enabled"] == settings.kubernetes_write_enabled

    assert policy_kwargs["allowed_namespaces"] == (settings.kubernetes_restart_allowed_namespaces)

    assert policy_kwargs["allowed_deployments"] == (settings.kubernetes_restart_allowed_deployments)

    assert policy_kwargs["subject"].username == "admin"

    mock_get_token.assert_called_once_with(
        name="ai-support-api",
        namespace="dev",
        config_mode=(settings.kubernetes_config_mode),
        context=settings.kubernetes_context,
    )

    # Most important recovery guarantee:
    # same token already exists in Kubernetes,
    # so do not patch a second time.
    mock_restart.assert_not_called()

    mock_monitor.assert_called_once()


@patch("ai_it_support_assistant.worker.action_worker.load_and_authorize_action_user")
@patch("ai_it_support_assistant.worker.action_worker.authorize_deployment_restart")
@patch("ai_it_support_assistant.worker.action_worker.monitor_deployment_rollout")
@patch("ai_it_support_assistant.worker.action_worker.restart_deployment")
@patch("ai_it_support_assistant.worker.action_worker.get_deployment_restart_token")
def test_restart_recovery_reuses_same_token(
    mock_get_token: Mock,
    mock_restart: Mock,
    mock_monitor: Mock,
    mock_authorize_deployment_restart: Mock,
    mock_load_user: Mock,
    db_session,
    settings,
) -> None:
    action = PendingAction(
        approval_id=(f"APR-RESTART-RECOVERY-{uuid4().hex[:8].upper()}"),
        action="restart_deployment",
        requested_by="admin",
        requested_roles_json='["admin"]',
        payload_json=(
            '{"name":"ai-support-api",'
            '"namespace":"dev",'
            '"evidence_desired_replicas":3,'
            '"evidence_ready_replicas":1,'
            '"evidence_available_replicas":1,'
            '"warnings":[]}'
        ),
        state="executing",
        version=3,
        resource_id="dev/ai-support-api",
        execution_token="T1",
    )

    save_pending_action(
        session=db_session,
        action=action,
    )

    db_session.commit()

    stored_action = get_pending_action(
        session=db_session,
        approval_id=action.approval_id,
    )

    assert stored_action is not None

    current_user = User(
        user_id=uuid4(),
        username="admin",
        roles=["admin"],
        disabled=False,
    )

    mock_load_user.return_value = current_user

    mock_authorize_deployment_restart.return_value = PolicyDecision(
        allowed=True,
        reason_code="allowed",
        reason=("Deployment restart reconciliation allowed."),
        policy_id="deployment-restart-v1",
        obligations=[
            "audit_execution",
            "verify_rollout",
        ],
    )

    # Kubernetes does not contain our persisted token.
    mock_get_token.return_value = "OLD"

    rollout_result = Mock()
    rollout_result.outcome = "healthy"

    rollout_result.model_dump_json.return_value = '{"outcome":"healthy"}'

    mock_monitor.return_value = rollout_result

    reconcile_stale_restart_action(
        action=stored_action,
        worker_id="worker-new",
        settings=settings,
    )

    mock_authorize_deployment_restart.assert_called_once()

    policy_kwargs = mock_authorize_deployment_restart.call_args.kwargs

    assert policy_kwargs["phase"] == "reconciliation"

    assert policy_kwargs["approval_state"] is None

    assert policy_kwargs["namespace"] == "dev"

    assert policy_kwargs["deployment_name"] == "ai-support-api"

    #
    # Kubernetes does not have T1,
    # so recovery may patch again,
    # but it MUST reuse the persisted T1.
    #
    mock_restart.assert_called_once()

    restart_kwargs = mock_restart.call_args.kwargs

    assert restart_kwargs["name"] == "ai-support-api"

    assert restart_kwargs["namespace"] == "dev"

    #
    # Critical idempotency assertion:
    # recovery reuses the existing token.
    #
    assert restart_kwargs["restart_timestamp"] == "T1"

    mock_monitor.assert_called_once()


def make_user(
    *,
    username: str = "it-support",
    roles: list[str] | None = None,
) -> User:
    return User(
        user_id=uuid4(),
        username=username,
        roles=roles or ["it_support"],
        disabled=False,
    )


def make_restart_action(
    *,
    requested_by: str = "alice",
    namespace: str = "team-a-dev",
    deployment_name: str = "api",
) -> PendingAction:
    payload = {
        "name": deployment_name,
        "namespace": namespace,
        "evidence_desired_replicas": 2,
        "evidence_ready_replicas": 2,
        "evidence_available_replicas": 2,
        "warnings": [],
    }

    return PendingAction(
        approval_id="APR-TEST-RESTART",
        requested_by=requested_by,
        action="restart_deployment",
        payload_json=json.dumps(payload),
        state="executing",
        version=1,
        worker_id="worker-test",
    )


def test_parse_restart_action_parses_restart_payload(
    db_session,
) -> None:

    action = make_restart_action(
        requested_by="alice",
        namespace="team-a-dev",
        deployment_name="api",
    )

    class FakeSettings:
        enable_write_actions = True

        allowed_restart_namespaces = {
            "team-a-dev",
        }

        allowed_restart_deployments = {
            "api",
        }

    payload = parse_restart_action(
        action=action,
    )

    assert payload.namespace == "team-a-dev"
    assert payload.name == "api"
