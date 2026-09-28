import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from ai_it_support_assistant.core.config import Settings
from ai_it_support_assistant.repositories.approval_repository import (
    ConcurrentActionUpdateError,
    claim_action_for_execution,
    get_pending_action,
    save_pending_action,
)
from ai_it_support_assistant.repositories.resource_permission_repository import (
    create_resource_permission,
)
from ai_it_support_assistant.schemas.approval import (
    PendingAction,
)
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.schemas.incident import (
    IncidentCreateRequest,
    IncidentRecord,
)
from ai_it_support_assistant.schemas.kubernetes import (
    DeploymentRolloutResult,
)
from ai_it_support_assistant.schemas.policy import (
    PolicyDecision,
)
from ai_it_support_assistant.services.action_execution_service import (
    ActionFailedError,
    ActionNotApprovedError,
    ActionRejectedError,
    IncidentExecutionError,
    KubernetesRestartExecutionError,
    execute_claimed_incident_action,
    execute_claimed_restart_action,
)
from ai_it_support_assistant.services.action_payload_service import (
    parse_incident_payload,
)
from ai_it_support_assistant.services.action_state_service import (
    InvalidActionTransitionError,
)
from ai_it_support_assistant.services.approval_service import (
    approve_pending_action,
    create_pending_incident_action,
    reject_pending_action,
)
from ai_it_support_assistant.services.kubernetes_state_service import (
    KubernetesResourceNotFoundError,
)
from ai_it_support_assistant.services.kubernetes_write_service import (
    KubernetesWriteError,
)
from ai_it_support_assistant.services.policy_enforcement_service import (
    AuthorizationDeniedError,
)


@pytest.fixture
def current_user() -> User:
    return User(
        user_id=UUID("11111111-1111-1111-1111-111111111111"),
        username="support",
        roles=["admin"],
        disabled=False,
    )


@pytest.fixture
def restart_admin_user() -> User:
    return User(
        user_id=UUID("22222222-2222-2222-2222-222222222222"),
        username="restart-admin",
        roles=["admin"],
        disabled=False,
    )


@pytest.fixture
def restart_settings() -> Settings:
    return Settings(
        kubernetes_write_enabled=True,
        kubernetes_restart_allowed_namespaces="dev",
        kubernetes_restart_allowed_deployments="ai-support-api",
        kubernetes_config_mode="kubeconfig",
        kubernetes_context="test-context",
    )


@pytest.fixture
def approved_restart_action(
    db_session,
    restart_admin_user,
) -> PendingAction:
    action = PendingAction(
        approval_id=f"APR-{uuid4().hex[:8].upper()}",
        action="restart_deployment",
        requested_by=restart_admin_user.username,
        payload_json=json.dumps(
            {
                "name": "ai-support-api",
                "namespace": "dev",
                "evidence_desired_replicas": 3,
                "evidence_ready_replicas": 1,
                "evidence_available_replicas": 1,
                "warnings": [],
            }
        ),
        state="approved",
        version=2,
        resource_id=None,
        execution_token=None,
        failure_reason=None,
    )

    save_pending_action(
        session=db_session,
        action=action,
    )

    db_session.commit()

    return action


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


@pytest.fixture
def restart_namespace_grant(
    db_session,
    restart_admin_user,
):
    grant = create_resource_permission(
        session=db_session,
        username=restart_admin_user.username,
        permission="deployment:restart",
        resource_type="namespace",
        resource_value="dev",
    )

    db_session.flush()

    return grant


def allowed_restart_execution_decision() -> PolicyDecision:
    return PolicyDecision(
        allowed=True,
        reason_code="allowed",
        reason="Deployment restart execution allowed.",
        policy_id="deployment-restart-v1",
        obligations=[
            "audit_execution",
            "verify_rollout",
        ],
    )


def allowed_incident_execution_decision() -> PolicyDecision:
    return PolicyDecision(
        allowed=True,
        reason_code="allowed",
        reason="Incident creation execution allowed.",
        policy_id="incident-create-v1",
        obligations=[
            "audit_execution",
        ],
    )


def denied_restart_execution_decision(
    *,
    reason_code: str,
    reason: str,
) -> PolicyDecision:
    return PolicyDecision(
        allowed=False,
        reason_code=reason_code,
        reason=reason,
        policy_id="deployment-restart-v1",
        obligations=[],
    )


def claim_for_test(
    *,
    session,
    action: PendingAction,
    worker_id: str = "worker-test-1",
) -> str:
    claim_action_for_execution(
        session=session,
        approval_id=action.approval_id,
        expected_version=action.version,
        worker_id=worker_id,
    )

    session.commit()

    return worker_id


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
        worker_id="worker-1",
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
            worker_id="worker-1",
        )

    db_session.rollback()


def test_pending_action_cannot_execute(
    db_session,
    pending_action,
    current_user: User,
) -> None:
    with pytest.raises(ActionNotApprovedError):
        execute_claimed_incident_action(
            session=db_session,
            approval_id=pending_action.approval_id,
            current_user=current_user,
            worker_id="worker-test-1",
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
        "ai_it_support_assistant.services.action_execution_service.create_incident",
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
        execute_claimed_incident_action(
            session=db_session,
            approval_id=pending_action.approval_id,
            current_user=current_user,
            worker_id="worker-test-1",
        )

    assert create_incident_calls == 0


def test_executing_action_cannot_be_claimed_again(
    db_session,
    approved_action,
) -> None:
    claim_action_for_execution(
        session=db_session,
        approval_id=approved_action.approval_id,
        expected_version=approved_action.version,
        worker_id="worker-1",
    )

    db_session.commit()

    current = get_pending_action(
        session=db_session,
        approval_id=approved_action.approval_id,
    )

    assert current is not None
    assert current.state == "executing"
    assert current.worker_id == "worker-1"

    with pytest.raises(ConcurrentActionUpdateError):
        claim_action_for_execution(
            session=db_session,
            approval_id=approved_action.approval_id,
            expected_version=current.version,
            worker_id="worker-2",
        )

    db_session.rollback()


def test_successful_incident_execution(
    monkeypatch: pytest.MonkeyPatch,
    db_session,
    approved_action,
    current_user: User,
) -> None:
    monkeypatch.setattr(
        "ai_it_support_assistant.services.action_execution_service.authorize_incident_create",
        lambda **kwargs: allowed_incident_execution_decision(),
    )

    worker_id = claim_for_test(
        session=db_session,
        action=approved_action,
    )

    result = execute_claimed_incident_action(
        session=db_session,
        approval_id=approved_action.approval_id,
        current_user=current_user,
        worker_id=worker_id,
    )

    assert result is not None

    saved = get_pending_action(
        session=db_session,
        approval_id=approved_action.approval_id,
    )

    assert saved is not None
    assert saved.state == "succeeded"
    assert saved.worker_id == worker_id


def test_external_failure_marks_action_failed(
    monkeypatch: pytest.MonkeyPatch,
    db_session,
    approved_action,
    current_user: User,
) -> None:

    monkeypatch.setattr(
        "ai_it_support_assistant.services.action_execution_service.authorize_incident_create",
        lambda **kwargs: allowed_incident_execution_decision(),
    )

    def fake_create_incident(**kwargs):
        raise RuntimeError("simulated external incident provider failure")

    monkeypatch.setattr(
        "ai_it_support_assistant.services.action_execution_service.create_incident",
        fake_create_incident,
    )

    worker_id = claim_for_test(
        session=db_session,
        action=approved_action,
    )

    with pytest.raises(IncidentExecutionError):
        execute_claimed_incident_action(
            session=db_session,
            approval_id=approved_action.approval_id,
            current_user=current_user,
            worker_id=worker_id,
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
    monkeypatch.setattr(
        "ai_it_support_assistant.services.action_execution_service.authorize_incident_create",
        lambda **kwargs: allowed_incident_execution_decision(),
    )
    create_incident_calls = 0

    def failing_create_incident(**kwargs):
        nonlocal create_incident_calls
        create_incident_calls += 1

        raise RuntimeError("simulated provider failure")

    monkeypatch.setattr(
        "ai_it_support_assistant.services.action_execution_service.create_incident",
        failing_create_incident,
    )

    worker_id = claim_for_test(
        session=db_session,
        action=approved_action,
    )

    with pytest.raises(IncidentExecutionError):
        execute_claimed_incident_action(
            session=db_session,
            approval_id=approved_action.approval_id,
            current_user=current_user,
            worker_id=worker_id,
        )

    assert create_incident_calls == 1

    with pytest.raises(ActionFailedError):
        execute_claimed_incident_action(
            session=db_session,
            approval_id=approved_action.approval_id,
            current_user=current_user,
            worker_id=worker_id,
        )

    assert create_incident_calls == 1


def test_retry_after_success_does_not_create_second_incident(
    monkeypatch: pytest.MonkeyPatch,
    db_session,
    approved_action,
    current_user: User,
) -> None:
    create_incident_calls = 0
    monkeypatch.setattr(
        "ai_it_support_assistant.services.action_execution_service.authorize_incident_create",
        lambda **kwargs: allowed_incident_execution_decision(),
    )

    expected_incident_id = f"INC-{uuid4().hex[:8].upper()}"

    incident_request = parse_incident_payload(approved_action.payload_json)

    fake_incident = IncidentRecord(
        incident_id=expected_incident_id,
        title=incident_request.title,
        description=incident_request.description,
        severity=incident_request.severity,
        service_name=incident_request.service_name,
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

    worker_id = claim_for_test(
        session=db_session,
        action=approved_action,
    )

    first = execute_claimed_incident_action(
        session=db_session,
        approval_id=approved_action.approval_id,
        current_user=current_user,
        worker_id=worker_id,
    )

    second = execute_claimed_incident_action(
        session=db_session,
        approval_id=approved_action.approval_id,
        current_user=current_user,
        worker_id=worker_id,
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


@patch("ai_it_support_assistant.services.action_execution_service.deployment_has_restart_token")
@patch("ai_it_support_assistant.services.action_execution_service.restart_deployment")
@patch("ai_it_support_assistant.services.action_execution_service.get_deployment_state")
@patch("ai_it_support_assistant.services.action_execution_service.monitor_deployment_rollout")
def test_restart_execution_token_is_persisted_before_write(
    mock_monitor_rollout,
    mock_get_deployment_state,
    mock_restart_deployment,
    mock_has_restart_token,
    monkeypatch: pytest.MonkeyPatch,
    db_session,
    restart_admin_user,
    restart_settings,
    approved_restart_action,
):
    monkeypatch.setattr(
        "ai_it_support_assistant.services.action_execution_service.authorize_deployment_restart",
        lambda **kwargs: allowed_restart_execution_decision(),
    )

    mock_has_restart_token.return_value = True

    def assert_token_exists_before_patch(
        **kwargs,
    ):
        saved = get_pending_action(
            session=db_session,
            approval_id=(approved_restart_action.approval_id),
        )

        assert saved is not None
        assert saved.state == "executing"
        assert saved.execution_token is not None

        assert kwargs["restart_timestamp"] == saved.execution_token

    mock_restart_deployment.side_effect = assert_token_exists_before_patch

    mock_monitor_rollout.return_value = DeploymentRolloutResult(
        deployment_name="ai-support-api",
        namespace="dev",
        outcome="healthy",
        desired_replicas=3,
        updated_replicas=3,
        ready_replicas=3,
        available_replicas=3,
        message=("Deployment rollout is healthy."),
    )

    worker_id = claim_for_test(
        session=db_session,
        action=approved_restart_action,
    )

    execute_claimed_restart_action(
        session=db_session,
        approval_id=(approved_restart_action.approval_id),
        current_user=restart_admin_user,
        worker_id=worker_id,
        settings=restart_settings,
    )

    mock_restart_deployment.assert_called_once()


@patch("ai_it_support_assistant.services.action_execution_service.monitor_deployment_rollout")
@patch("ai_it_support_assistant.services.action_execution_service.deployment_has_restart_token")
@patch("ai_it_support_assistant.services.action_execution_service.restart_deployment")
@patch("ai_it_support_assistant.services.action_execution_service.get_deployment_state")
def test_restart_action_succeeds_when_marker_is_verified(
    mock_get_deployment_state,
    mock_restart_deployment,
    mock_has_restart_token,
    mock_monitor_rollout,
    monkeypatch: pytest.MonkeyPatch,
    db_session,
    restart_admin_user,
    approved_restart_action,
):
    monkeypatch.setattr(
        "ai_it_support_assistant.services.action_execution_service.authorize_deployment_restart",
        lambda **kwargs: allowed_restart_execution_decision(),
    )

    settings = Settings(
        kubernetes_write_enabled=True,
        kubernetes_restart_allowed_namespaces="dev",
        kubernetes_restart_allowed_deployments=("ai-support-api"),
        kubernetes_config_mode="kubeconfig",
        kubernetes_context="test-context",
    )

    mock_restart_deployment.return_value = None
    mock_has_restart_token.return_value = True

    mock_monitor_rollout.return_value = DeploymentRolloutResult(
        deployment_name="ai-support-api",
        namespace="dev",
        outcome="healthy",
        desired_replicas=3,
        updated_replicas=3,
        ready_replicas=3,
        available_replicas=3,
        message=("Deployment rollout is healthy."),
    )

    worker_id = claim_for_test(
        session=db_session,
        action=approved_restart_action,
    )

    result = execute_claimed_restart_action(
        session=db_session,
        approval_id=(approved_restart_action.approval_id),
        current_user=restart_admin_user,
        worker_id=worker_id,
        settings=settings,
    )

    assert result.state == "succeeded"
    assert result.resource_id == "dev/ai-support-api"
    assert result.execution_token is not None

    saved = get_pending_action(
        session=db_session,
        approval_id=(approved_restart_action.approval_id),
    )

    assert saved is not None
    assert saved.state == "succeeded"
    assert saved.resource_id == "dev/ai-support-api"
    assert saved.execution_token is not None

    mock_restart_deployment.assert_called_once()


@patch("ai_it_support_assistant.services.action_execution_service.deployment_has_restart_token")
@patch("ai_it_support_assistant.services.action_execution_service.restart_deployment")
@patch("ai_it_support_assistant.services.action_execution_service.get_deployment_state")
@patch("ai_it_support_assistant.services.action_execution_service.monitor_deployment_rollout")
def test_restart_succeeds_after_reconciliation(
    mock_monitor_rollout,
    mock_get_deployment_state,
    mock_restart_deployment,
    mock_has_restart_token,
    monkeypatch: pytest.MonkeyPatch,
    db_session,
    restart_admin_user,
    restart_settings,
    approved_restart_action,
):
    monkeypatch.setattr(
        "ai_it_support_assistant.services.action_execution_service.authorize_deployment_restart",
        lambda **kwargs: allowed_restart_execution_decision(),
    )

    mock_restart_deployment.side_effect = KubernetesWriteError("timeout")

    mock_has_restart_token.return_value = True

    mock_monitor_rollout.return_value = DeploymentRolloutResult(
        deployment_name="ai-support-api",
        namespace="dev",
        outcome="healthy",
        desired_replicas=3,
        updated_replicas=3,
        ready_replicas=3,
        available_replicas=3,
        message=("Deployment rollout is healthy."),
    )

    worker_id = claim_for_test(
        session=db_session,
        action=approved_restart_action,
    )

    result = execute_claimed_restart_action(
        session=db_session,
        approval_id=(approved_restart_action.approval_id),
        current_user=restart_admin_user,
        worker_id=worker_id,
        settings=restart_settings,
    )

    assert result.state == "succeeded"
    assert result.execution_token is not None

    mock_restart_deployment.assert_called_once()
    mock_has_restart_token.assert_called_once()


@patch("ai_it_support_assistant.services.action_execution_service.deployment_has_restart_token")
@patch("ai_it_support_assistant.services.action_execution_service.restart_deployment")
@patch("ai_it_support_assistant.services.action_execution_service.get_deployment_state")
def test_restart_fails_when_reconciliation_fails(
    mock_get_deployment_state,
    mock_restart_deployment,
    mock_has_restart_token,
    monkeypatch: pytest.MonkeyPatch,
    db_session,
    restart_admin_user,
    restart_settings,
    approved_restart_action,
):
    monkeypatch.setattr(
        "ai_it_support_assistant.services.action_execution_service.authorize_deployment_restart",
        lambda **kwargs: allowed_restart_execution_decision(),
    )

    mock_restart_deployment.side_effect = KubernetesWriteError("timeout")

    mock_has_restart_token.return_value = False

    worker_id = claim_for_test(
        session=db_session,
        action=approved_restart_action,
    )

    with pytest.raises(KubernetesRestartExecutionError):
        execute_claimed_restart_action(
            session=db_session,
            approval_id=(approved_restart_action.approval_id),
            current_user=restart_admin_user,
            worker_id=worker_id,
            settings=restart_settings,
        )

    saved = get_pending_action(
        session=db_session,
        approval_id=(approved_restart_action.approval_id),
    )

    assert saved is not None
    assert saved.state == "failed"

    mock_restart_deployment.assert_called_once()


@patch("ai_it_support_assistant.services.action_execution_service.restart_deployment")
@patch("ai_it_support_assistant.services.action_execution_service.authorize_deployment_restart")
def test_restart_policy_is_rechecked_before_execution(
    mock_authorize_deployment_restart,
    mock_restart_deployment,
    db_session,
    restart_admin_user,
    restart_settings,
    approved_restart_action,
):
    restart_settings.kubernetes_restart_allowed_deployments = "some-other-deployment"

    mock_authorize_deployment_restart.return_value = denied_restart_execution_decision(
        reason_code=("deployment_not_globally_allowed"),
        reason=("Deployment is not globally allowed for restart."),
    )

    worker_id = claim_for_test(
        session=db_session,
        action=approved_restart_action,
    )

    with pytest.raises(AuthorizationDeniedError) as exc_info:
        execute_claimed_restart_action(
            session=db_session,
            approval_id=(approved_restart_action.approval_id),
            current_user=restart_admin_user,
            worker_id=worker_id,
            settings=restart_settings,
        )

    assert exc_info.value.decision.reason_code == "deployment_not_globally_allowed"

    call_kwargs = mock_authorize_deployment_restart.call_args.kwargs

    assert call_kwargs["phase"] == "execution"

    assert call_kwargs["approval_state"] == "approved"

    assert call_kwargs["namespace"] == "dev"

    assert call_kwargs["deployment_name"] == "ai-support-api"

    assert call_kwargs["writes_enabled"] is True

    assert call_kwargs["allowed_namespaces"] == "dev"

    assert call_kwargs["allowed_deployments"] == "some-other-deployment"

    assert call_kwargs["session"] is db_session

    assert call_kwargs["subject"].username == restart_admin_user.username

    mock_restart_deployment.assert_not_called()


@patch("ai_it_support_assistant.services.action_execution_service.restart_deployment")
@patch("ai_it_support_assistant.services.action_execution_service.get_deployment_state")
def test_restart_does_not_patch_when_deployment_disappears(
    mock_get_deployment_state,
    mock_restart_deployment,
    monkeypatch: pytest.MonkeyPatch,
    db_session,
    restart_admin_user,
    restart_settings,
    approved_restart_action,
):
    monkeypatch.setattr(
        "ai_it_support_assistant.services.action_execution_service.authorize_deployment_restart",
        lambda **kwargs: allowed_restart_execution_decision(),
    )

    mock_get_deployment_state.side_effect = KubernetesResourceNotFoundError(
        "Deployment was not found."
    )

    worker_id = claim_for_test(
        session=db_session,
        action=approved_restart_action,
    )

    with pytest.raises(KubernetesResourceNotFoundError):
        execute_claimed_restart_action(
            session=db_session,
            approval_id=(approved_restart_action.approval_id),
            current_user=restart_admin_user,
            worker_id=worker_id,
            settings=restart_settings,
        )

    mock_restart_deployment.assert_not_called()


@patch("ai_it_support_assistant.services.action_execution_service.create_incident")
@patch("ai_it_support_assistant.services.action_execution_service.authorize_incident_create")
def test_incident_policy_is_rechecked_before_execution(
    mock_authorize_incident_create,
    mock_create_incident,
    db_session,
    approved_action,
    current_user,
):
    mock_authorize_incident_create.return_value = PolicyDecision(
        allowed=False,
        reason_code="missing_permission",
        reason=("Required capability permission is missing."),
        policy_id="global-permission-v1",
        obligations=[],
    )

    worker_id = claim_for_test(
        session=db_session,
        action=approved_action,
    )

    with pytest.raises(AuthorizationDeniedError) as exc_info:
        execute_claimed_incident_action(
            session=db_session,
            approval_id=(approved_action.approval_id),
            current_user=current_user,
            worker_id=worker_id,
        )

    assert exc_info.value.decision.reason_code == "missing_permission"

    call_kwargs = mock_authorize_incident_create.call_args.kwargs

    assert call_kwargs["phase"] == "execution"
    assert call_kwargs["approval_state"] == "approved"

    assert call_kwargs["session"] is db_session

    mock_create_incident.assert_not_called()
