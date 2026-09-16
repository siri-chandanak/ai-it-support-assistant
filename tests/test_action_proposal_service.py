from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.schemas.incident import (
    IncidentCreateRequest,
)
from ai_it_support_assistant.schemas.policy import (
    PolicyContext,
    PolicyDecision,
    PolicyRequest,
    PolicyResource,
    PolicySubject,
)
from ai_it_support_assistant.services.action_proposal_service import (
    prepare_incident_action,
    prepare_restart_action,
)
from ai_it_support_assistant.services.kubernetes_restart_validation_service import (
    KubernetesRestartValidationError,
)
from ai_it_support_assistant.services.policy_enforcement_service import (
    AuthorizationDeniedError,
)
from ai_it_support_assistant.services.policy_service import (
    evaluate_policy,
)


def make_user(
    *,
    username: str,
    roles: list[str],
) -> User:
    return User(
        user_id=uuid4(),
        username=username,
        roles=roles,
        disabled=False,
    )


def allowed_restart_decision() -> PolicyDecision:
    return PolicyDecision(
        allowed=True,
        reason_code="allowed",
        reason="Deployment restart policy allowed.",
        policy_id="deployment-restart-v1",
        obligations=[
            "explicit_approval",
            "audit_execution",
            "verify_rollout",
        ],
    )


def allowed_incident_proposal_decision() -> PolicyDecision:
    return PolicyDecision(
        allowed=True,
        reason_code="allowed",
        reason="Incident creation allowed.",
        policy_id="incident-create-v1",
        obligations=[
            "explicit_approval",
            "audit_execution",
        ],
    )


def test_prepare_incident_action_creates_pending_action(
    monkeypatch,
):
    user = make_user(
        username="it-support",
        roles=["it_support"],
    )

    request = IncidentCreateRequest(
        title="VPN authentication degradation",
        description=("Multiple users are reporting elevated authentication latency."),
        severity="medium",
        service_name="vpn-gateway",
    )

    captured: dict[str, object] = {}

    class FakePendingAction:
        approval_id = "APR-INCIDENT1"
        state = "pending"
        action = "create_incident"

    def fake_create_pending_incident_action(
        *,
        session,
        requested_by,
        incident,
    ):
        captured["requested_by"] = requested_by
        captured["incident"] = incident

        return FakePendingAction()

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.action_proposal_service.create_pending_incident_action"),
        fake_create_pending_incident_action,
    )

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.action_proposal_service.authorize_incident_create"),
        lambda **kwargs: PolicyDecision(
            allowed=True,
            reason_code="allowed",
            reason="Incident creation allowed.",
            policy_id="incident-create-v1",
            obligations=[
                "explicit_approval",
                "audit_execution",
            ],
        ),
    )

    fake_session = object()

    pending = prepare_incident_action(
        session=fake_session,
        current_user=user,
        request=request,
    )

    assert pending.approval_id == "APR-INCIDENT1"
    assert pending.state == "pending"
    assert pending.action == "create_incident"

    assert captured["requested_by"] == "it-support"
    assert captured["incident"] == request


def test_prepare_incident_action_rejects_reader(
    monkeypatch,
):
    user = make_user(
        username="reader",
        roles=["reader"],
    )

    request = IncidentCreateRequest(
        title="VPN authentication degradation",
        description=("Multiple users are reporting elevated authentication latency."),
        severity="medium",
        service_name="vpn-gateway",
    )

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.action_proposal_service.authorize_incident_create"),
        lambda **kwargs: PolicyDecision(
            allowed=False,
            reason_code="missing_permission",
            reason=("Required capability permission is missing."),
            policy_id="global-permission-v1",
            obligations=[],
        ),
    )

    with pytest.raises(AuthorizationDeniedError) as exc_info:
        prepare_incident_action(
            session=object(),
            current_user=user,
            request=request,
        )

    assert exc_info.value.decision.reason_code == "missing_permission"

    assert exc_info.value.decision.policy_id == "global-permission-v1"


def test_prepare_restart_action_creates_pending_action(
    monkeypatch,
):
    user = make_user(
        username="admin",
        roles=["admin"],
    )
    monkeypatch.setattr(
        "ai_it_support_assistant.services.action_proposal_service.authorize_deployment_restart",
        lambda **kwargs: allowed_restart_decision(),
    )

    captured: dict[str, object] = {}

    class FakeSettings:
        mcp_issuer_url = "http://127.0.0.1:8000"
        mcp_resource_server_url = "http://127.0.0.1:8001/mcp"

        kubernetes_write_enabled = True
        kubernetes_restart_allowed_namespaces = "ai-it-support-test"
        kubernetes_restart_allowed_deployments = "demo-api"
        kubernetes_config_mode = "local"
        kubernetes_context = "kind-kin"

    class FakeDeploymentState:
        name = "demo-api"
        namespace = "ai-it-support-test"
        desired_replicas = 2
        ready_replicas = 2
        available_replicas = 2

    class FakePendingAction:
        approval_id = "APR-RESTART1"
        state = "pending"
        action = "restart_deployment"

    def fake_get_deployment_state(
        *,
        name,
        namespace,
        config_mode,
        context,
    ):
        captured["deployment_name"] = name
        captured["namespace"] = namespace

        return FakeDeploymentState()

    def fake_create_pending_action(
        *,
        session,
        requested_by,
        action_type,
        payload_json,
    ):
        captured["requested_by"] = requested_by
        captured["action_type"] = action_type
        captured["payload_json"] = payload_json

        return FakePendingAction()

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.action_proposal_service.get_deployment_state"),
        fake_get_deployment_state,
    )

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.action_proposal_service.create_pending_action"),
        fake_create_pending_action,
    )

    pending, payload = prepare_restart_action(
        session=object(),
        current_user=user,
        deployment_name="demo-api",
        namespace="ai-it-support-test",
        kubernetes_write_enabled=True,
        kubernetes_restart_allowed_namespaces=("ai-it-support-test"),
        kubernetes_restart_allowed_deployments=("demo-api"),
        kubernetes_config_mode="local",
        kubernetes_context="kind-kin",
    )

    assert pending.approval_id == "APR-RESTART1"
    assert pending.state == "pending"
    assert pending.action == "restart_deployment"

    assert payload.name == "demo-api"
    assert payload.namespace == "ai-it-support-test"
    assert payload.evidence_desired_replicas == 2
    assert payload.evidence_ready_replicas == 2
    assert payload.evidence_available_replicas == 2
    assert payload.warnings == []

    assert captured["requested_by"] == "admin"
    assert captured["action_type"] == "restart_deployment"


def test_prepare_restart_action_rejects_non_admin(
    monkeypatch,
):
    user = make_user(
        username="it-support",
        roles=["it_support"],
    )

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.action_proposal_service.authorize_deployment_restart"),
        lambda **kwargs: PolicyDecision(
            allowed=False,
            reason_code="missing_permission",
            reason=("Required capability permission is missing."),
            policy_id="global-permission-v1",
            obligations=[],
        ),
    )

    with pytest.raises(AuthorizationDeniedError) as exc_info:
        prepare_restart_action(
            session=object(),
            current_user=user,
            deployment_name="demo-api",
            namespace="ai-it-support-test",
            kubernetes_write_enabled=True,
            kubernetes_restart_allowed_namespaces=("ai-it-support-test"),
            kubernetes_restart_allowed_deployments=("demo-api"),
            kubernetes_config_mode="local",
            kubernetes_context="kind-kin",
        )

    assert exc_info.value.decision.reason_code == "missing_permission"

    assert exc_info.value.decision.policy_id == "global-permission-v1"


def test_prepare_restart_action_rejects_zero_replicas(
    monkeypatch,
):
    user = make_user(
        username="admin",
        roles=["admin"],
    )

    monkeypatch.setattr(
        "ai_it_support_assistant.services.action_proposal_service.authorize_deployment_restart",
        lambda **kwargs: allowed_restart_decision(),
    )

    class FakeSettings:
        mcp_issuer_url = "http://127.0.0.1:8000"
        mcp_resource_server_url = "http://127.0.0.1:8001/mcp"

        kubernetes_write_enabled = True
        kubernetes_restart_allowed_namespaces = "ai-it-support-test"
        kubernetes_restart_allowed_deployments = "demo-api"
        kubernetes_config_mode = "local"
        kubernetes_context = "kind-kin"

    class FakeDeploymentState:
        name = "demo-api"
        namespace = "ai-it-support-test"
        desired_replicas = 0
        ready_replicas = 0
        available_replicas = 0

    def fake_get_deployment_state(
        *,
        name,
        namespace,
        config_mode,
        context,
    ):
        return FakeDeploymentState()

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.action_proposal_service.get_deployment_state"),
        fake_get_deployment_state,
    )

    with pytest.raises(
        KubernetesRestartValidationError,
        match="zero desired replicas",
    ):
        prepare_restart_action(
            session=object(),
            current_user=user,
            deployment_name="demo-api",
            namespace="ai-it-support-test",
            kubernetes_write_enabled=True,
            kubernetes_restart_allowed_namespaces=("ai-it-support-test"),
            kubernetes_restart_allowed_deployments=("demo-api"),
            kubernetes_config_mode="local",
            kubernetes_context="kind-kin",
        )


def test_prepare_restart_action_adds_single_replica_warning(
    monkeypatch,
):
    user = make_user(
        username="admin",
        roles=["admin"],
    )

    monkeypatch.setattr(
        "ai_it_support_assistant.services.action_proposal_service.authorize_deployment_restart",
        lambda **kwargs: allowed_restart_decision(),
    )

    class FakeSettings:
        mcp_issuer_url = "http://127.0.0.1:8000"
        mcp_resource_server_url = "http://127.0.0.1:8001/mcp"

        kubernetes_write_enabled = True
        kubernetes_restart_allowed_namespaces = "ai-it-support-test"
        kubernetes_restart_allowed_deployments = "demo-api"
        kubernetes_config_mode = "local"
        kubernetes_context = "kind-kin"

    class FakeDeploymentState:
        name = "demo-api"
        namespace = "ai-it-support-test"
        desired_replicas = 1
        ready_replicas = 1
        available_replicas = 1

    class FakePendingAction:
        approval_id = "APR-RESTART2"
        state = "pending"
        action = "restart_deployment"

    def fake_get_deployment_state(
        *,
        name,
        namespace,
        config_mode,
        context,
    ):
        return FakeDeploymentState()

    def fake_create_pending_action(
        *,
        session,
        requested_by,
        action_type,
        payload_json,
    ):
        return FakePendingAction()

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.action_proposal_service.get_deployment_state"),
        fake_get_deployment_state,
    )

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.action_proposal_service.create_pending_action"),
        fake_create_pending_action,
    )

    _, payload = prepare_restart_action(
        session=object(),
        current_user=user,
        deployment_name="demo-api",
        namespace="ai-it-support-test",
        kubernetes_write_enabled=True,
        kubernetes_restart_allowed_namespaces=("ai-it-support-test"),
        kubernetes_restart_allowed_deployments=("demo-api"),
        kubernetes_config_mode="local",
        kubernetes_context="kind-kin",
    )

    assert len(payload.warnings) == 1
    assert "temporary unavailability" in payload.warnings[0]


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


def test_incident_proposal_allowed() -> None:
    session = MagicMock(spec=Session)

    request = PolicyRequest(
        subject=build_subject(
            permissions=["incident:create"],
        ),
        action="incident.create",
        resource=PolicyResource(
            resource_type="incident",
        ),
        context=PolicyContext(
            attributes={
                "phase": "proposal",
                "approval_state": None,
            },
        ),
    )

    decision = evaluate_policy(
        request=request,
        session=session,
    )

    assert decision.allowed is True
    assert "explicit_approval" in decision.obligations


def test_incident_proposal_denied_without_permission() -> None:
    session = MagicMock(spec=Session)

    request = PolicyRequest(
        subject=build_subject(
            permissions=[],
        ),
        action="incident.create",
        resource=PolicyResource(
            resource_type="incident",
        ),
        context=PolicyContext(
            attributes={
                "phase": "proposal",
                "approval_state": None,
            },
        ),
    )

    decision = evaluate_policy(
        request=request,
        session=session,
    )

    assert decision.allowed is False
    assert decision.reason_code == "missing_permission"
