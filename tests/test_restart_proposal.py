from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from ai_it_support_assistant.repositories.resource_permission_repository import (
    create_resource_permission,
)
from ai_it_support_assistant.schemas.approval import PendingAction
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.schemas.kubernetes import (
    DeploymentRestartActionPayload,
)
from ai_it_support_assistant.services.action_proposal_service import (
    prepare_restart_action,
)
from ai_it_support_assistant.services.agent_router_service import (
    AgentRoutingError,
)
from ai_it_support_assistant.services.agent_service import (
    handle_agent_request,
)
from ai_it_support_assistant.services.kubernetes_write_policy_service import (
    KubernetesWritePolicyError,
)
from ai_it_support_assistant.services.resource_authorization_service import (
    ResourcePermissionDeniedError,
)
from ai_it_support_assistant.services.tool_authorization_service import (
    ToolAuthorizationError,
)

AGENT_SERVICE_PATH = "ai_it_support_assistant.services.agent_service"

ACTION_PROPOSAL_SERVICE_PATH = "ai_it_support_assistant.services.action_proposal_service"


def make_user(
    *,
    username: str = "admin",
    roles: list[str] | None = None,
) -> MagicMock:
    user = MagicMock()
    user.username = username
    user.roles = roles or ["admin"]
    return user


def make_restart_decision(
    *,
    deployment_name: str | None = "payment-api",
    namespace: str | None = "dev",
) -> SimpleNamespace:
    return SimpleNamespace(
        action="restart_deployment",
        service_name=None,
        kubernetes_resource_type="deployment",
        kubernetes_resource_name=deployment_name,
        kubernetes_namespace=namespace,
        incident_title=None,
        incident_description=None,
        incident_severity=None,
        reasoning_summary=("User explicitly requested a Deployment restart."),
    )


def make_deployment_state(
    *,
    desired_replicas: int = 3,
    ready_replicas: int = 1,
    available_replicas: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        resource_type="deployment",
        name="payment-api",
        namespace="dev",
        desired_replicas=desired_replicas,
        ready_replicas=ready_replicas,
        available_replicas=available_replicas,
    )


def make_pending_action(
    *,
    username: str = "admin",
) -> PendingAction:
    return PendingAction(
        approval_id="APR-12345678",
        action="restart_deployment",
        requested_by=username,
        payload_json="{}",
        state="pending",
        version=1,
        resource_id=None,
        execution_token=None,
        failure_reason=None,
    )


def call_agent(
    *,
    current_user: MagicMock | None = None,
    session: MagicMock | None = None,
) -> object:
    return handle_agent_request(
        question=("Restart payment-api deployment in dev."),
        current_user=(current_user if current_user is not None else make_user()),
        session=(session if session is not None else MagicMock()),
        embedding_model_name=("sentence-transformers/all-MiniLM-L6-v2"),
        qdrant_url="http://localhost:6333",
        collection_name="document_chunks",
        qdrant_timeout_seconds=5.0,
        qdrant_max_attempts=3,
        rag_top_k=3,
        rag_score_threshold=0.5,
        openai_api_key="test-key",
        llm_model="test-model",
        openai_timeout_seconds=10.0,
        openai_max_retries=1,
        kubernetes_config_mode="kubeconfig",
        kubernetes_context="dev-context",
        kubernetes_default_namespace="default",
        kubernetes_write_enabled=True,
        kubernetes_restart_allowed_namespaces=("dev,development"),
        kubernetes_restart_allowed_deployments=("payment-api,vpn-api"),
        embedding_cache_enabled=False,
        retrieval_cache_enabled=False,
    )


@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.create_pending_action")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.get_deployment_state")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.validate_restart_policy")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.authorize_tool")
@patch(f"{AGENT_SERVICE_PATH}.route_agent_request")
def test_restart_proposal_requires_approval(
    mock_route_agent_request,
    mock_authorize_tool,
    mock_validate_restart_policy,
    mock_get_deployment_state,
    mock_create_pending_action,
) -> None:
    mock_route_agent_request.return_value = make_restart_decision()

    mock_get_deployment_state.return_value = make_deployment_state()

    mock_create_pending_action.return_value = make_pending_action()

    session = MagicMock()

    response = call_agent(
        session=session,
    )

    assert response.action == "restart_deployment"
    assert response.approval_required is True
    assert response.approval_id == "APR-12345678"

    assert response.proposed_restart is not None

    assert response.proposed_restart.name == "payment-api"

    assert response.proposed_restart.namespace == "dev"

    assert response.proposed_restart.evidence_desired_replicas == 3

    assert response.proposed_restart.evidence_ready_replicas == 1

    assert response.proposed_restart.evidence_available_replicas == 1

    assert response.proposed_restart.warnings == []

    mock_authorize_tool.assert_called_once()

    authorize_kwargs = mock_authorize_tool.call_args.kwargs

    assert authorize_kwargs["tool_name"] == "restart_deployment"

    mock_validate_restart_policy.assert_called_once_with(
        namespace="dev",
        deployment_name="payment-api",
        write_enabled=True,
        allowed_namespaces_raw=("dev,development"),
        allowed_deployments_raw=("payment-api,vpn-api"),
    )

    mock_get_deployment_state.assert_called_once_with(
        name="payment-api",
        namespace="dev",
        config_mode="kubeconfig",
        context="dev-context",
    )

    mock_create_pending_action.assert_called_once()
    session.commit.assert_called_once()


@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.create_pending_action")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.get_deployment_state")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.validate_restart_policy")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.authorize_tool")
@patch(f"{AGENT_SERVICE_PATH}.route_agent_request")
def test_restart_proposal_stores_validated_payload(
    mock_route_agent_request,
    mock_authorize_tool,
    mock_validate_restart_policy,
    mock_get_deployment_state,
    mock_create_pending_action,
) -> None:
    mock_route_agent_request.return_value = make_restart_decision()

    mock_get_deployment_state.return_value = make_deployment_state(
        desired_replicas=3,
        ready_replicas=2,
        available_replicas=2,
    )

    mock_create_pending_action.return_value = make_pending_action()

    call_agent()

    call_kwargs = mock_create_pending_action.call_args.kwargs

    assert call_kwargs["requested_by"] == "admin"

    assert call_kwargs["action_type"] == "restart_deployment"

    payload = DeploymentRestartActionPayload.model_validate_json(call_kwargs["payload_json"])

    assert payload.name == "payment-api"
    assert payload.namespace == "dev"
    assert payload.evidence_desired_replicas == 3
    assert payload.evidence_ready_replicas == 2
    assert payload.evidence_available_replicas == 2
    assert payload.warnings == []


@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.create_pending_action")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.get_deployment_state")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.validate_restart_policy")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.authorize_tool")
@patch(f"{AGENT_SERVICE_PATH}.route_agent_request")
def test_restart_proposal_warns_for_single_replica(
    mock_route_agent_request,
    mock_authorize_tool,
    mock_validate_restart_policy,
    mock_get_deployment_state,
    mock_create_pending_action,
) -> None:
    mock_route_agent_request.return_value = make_restart_decision()

    mock_get_deployment_state.return_value = make_deployment_state(
        desired_replicas=1,
        ready_replicas=1,
        available_replicas=1,
    )

    mock_create_pending_action.return_value = make_pending_action()

    response = call_agent()

    assert response.proposed_restart is not None

    assert response.proposed_restart.warnings == [
        ("Deployment has one desired replica; restart may cause temporary unavailability.")
    ]

    mock_create_pending_action.assert_called_once()


@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.create_pending_action")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.get_deployment_state")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.validate_restart_policy")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.authorize_tool")
@patch(f"{AGENT_SERVICE_PATH}.route_agent_request")
def test_restart_proposal_rejects_zero_replicas(
    mock_route_agent_request,
    mock_authorize_tool,
    mock_validate_restart_policy,
    mock_get_deployment_state,
    mock_create_pending_action,
) -> None:
    mock_route_agent_request.return_value = make_restart_decision()

    mock_get_deployment_state.return_value = make_deployment_state(
        desired_replicas=0,
        ready_replicas=0,
        available_replicas=0,
    )

    with pytest.raises(
        KubernetesWritePolicyError,
        match="zero desired replicas",
    ):
        call_agent()

    mock_create_pending_action.assert_not_called()


@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.create_pending_action")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.get_deployment_state")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.validate_restart_policy")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.authorize_tool")
@patch(f"{AGENT_SERVICE_PATH}.route_agent_request")
def test_unauthorized_user_cannot_propose_restart(
    mock_route_agent_request,
    mock_authorize_tool,
    mock_validate_restart_policy,
    mock_get_deployment_state,
    mock_create_pending_action,
) -> None:
    mock_route_agent_request.return_value = make_restart_decision()

    mock_authorize_tool.side_effect = ToolAuthorizationError("Tool access denied.")

    current_user = make_user(
        username="reader",
        roles=["reader"],
    )

    with pytest.raises(ToolAuthorizationError):
        call_agent(
            current_user=current_user,
        )

    mock_validate_restart_policy.assert_not_called()
    mock_get_deployment_state.assert_not_called()
    mock_create_pending_action.assert_not_called()


@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.create_pending_action")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.get_deployment_state")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.validate_restart_policy")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.authorize_tool")
@patch(f"{AGENT_SERVICE_PATH}.route_agent_request")
def test_admin_cannot_bypass_namespace_policy(
    mock_route_agent_request,
    mock_authorize_tool,
    mock_validate_restart_policy,
    mock_get_deployment_state,
    mock_create_pending_action,
) -> None:
    mock_route_agent_request.return_value = make_restart_decision(
        namespace="production",
    )

    mock_validate_restart_policy.side_effect = KubernetesWritePolicyError(
        "Namespace is not approved."
    )

    with pytest.raises(
        KubernetesWritePolicyError,
        match="Namespace is not approved",
    ):
        call_agent()

    mock_get_deployment_state.assert_not_called()
    mock_create_pending_action.assert_not_called()


@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.create_pending_action")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.get_deployment_state")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.validate_restart_policy")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.authorize_tool")
@patch(f"{AGENT_SERVICE_PATH}.route_agent_request")
def test_admin_cannot_bypass_deployment_policy(
    mock_route_agent_request,
    mock_authorize_tool,
    mock_validate_restart_policy,
    mock_get_deployment_state,
    mock_create_pending_action,
) -> None:
    mock_route_agent_request.return_value = make_restart_decision(
        deployment_name=("identity-controller"),
    )

    mock_validate_restart_policy.side_effect = KubernetesWritePolicyError(
        "Deployment is not approved."
    )

    with pytest.raises(
        KubernetesWritePolicyError,
        match="Deployment is not approved",
    ):
        call_agent()

    mock_get_deployment_state.assert_not_called()
    mock_create_pending_action.assert_not_called()


@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.create_pending_action")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.get_deployment_state")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.validate_restart_policy")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.authorize_tool")
@patch(f"{AGENT_SERVICE_PATH}.route_agent_request")
def test_restart_requires_explicit_namespace(
    mock_route_agent_request,
    mock_authorize_tool,
    mock_validate_restart_policy,
    mock_get_deployment_state,
    mock_create_pending_action,
) -> None:
    mock_route_agent_request.return_value = make_restart_decision(
        namespace=None,
    )

    with pytest.raises(
        AgentRoutingError,
        match="Namespace is required",
    ):
        call_agent()

    mock_authorize_tool.assert_not_called()
    mock_validate_restart_policy.assert_not_called()
    mock_get_deployment_state.assert_not_called()
    mock_create_pending_action.assert_not_called()


@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.create_pending_action")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.get_deployment_state")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.validate_restart_policy")
@patch(f"{ACTION_PROPOSAL_SERVICE_PATH}.authorize_tool")
@patch(f"{AGENT_SERVICE_PATH}.route_agent_request")
def test_restart_requires_deployment_name(
    mock_route_agent_request,
    mock_authorize_tool,
    mock_validate_restart_policy,
    mock_get_deployment_state,
    mock_create_pending_action,
) -> None:
    mock_route_agent_request.return_value = make_restart_decision(
        deployment_name=None,
    )

    with pytest.raises(
        AgentRoutingError,
        match="Deployment name is required",
    ):
        call_agent()

    mock_authorize_tool.assert_not_called()
    mock_validate_restart_policy.assert_not_called()
    mock_get_deployment_state.assert_not_called()
    mock_create_pending_action.assert_not_called()


def test_restart_denied_without_namespace_grant(
    db_session,
) -> None:
    user = User(
        user_id=uuid4(),
        username="alice",
        roles=["admin"],
        disabled=False,
    )

    with pytest.raises(
        ResourcePermissionDeniedError,
    ):
        prepare_restart_action(
            session=db_session,
            current_user=user,
            deployment_name="api",
            namespace="team-a-dev",
            kubernetes_write_enabled=True,
            kubernetes_restart_allowed_namespaces="team-a-dev",
            kubernetes_restart_allowed_deployments="api",
            kubernetes_config_mode="mock",
            kubernetes_context="",
        )


def test_restart_allowed_with_namespace_grant(
    db_session,
    monkeypatch,
) -> None:
    user = User(
        user_id=uuid4(),
        username="alice",
        roles=["admin"],
        disabled=False,
    )

    create_resource_permission(
        session=db_session,
        username="alice",
        permission="deployment:restart",
        resource_type="namespace",
        resource_value="team-a-dev",
    )

    class FakeDeploymentState:
        name = "api"
        namespace = "team-a-dev"
        desired_replicas = 2
        ready_replicas = 2
        available_replicas = 2

    monkeypatch.setattr(
        "ai_it_support_assistant.services.action_proposal_service.get_deployment_state",
        lambda **kwargs: FakeDeploymentState(),
    )

    pending, restart_payload = prepare_restart_action(
        session=db_session,
        current_user=user,
        deployment_name="api",
        namespace="team-a-dev",
        kubernetes_write_enabled=True,
        kubernetes_restart_allowed_namespaces="team-a-dev",
        kubernetes_restart_allowed_deployments="api",
        kubernetes_config_mode="local",
        kubernetes_context="kind-kin",
    )

    assert pending is not None
    assert restart_payload.name == "api"
    assert restart_payload.namespace == "team-a-dev"


def test_restart_denied_for_different_namespace(
    db_session,
) -> None:
    user = User(
        user_id=uuid4(),
        username="alice",
        roles=["admin"],
        disabled=False,
    )

    create_resource_permission(
        session=db_session,
        username="alice",
        permission="deployment:restart",
        resource_type="namespace",
        resource_value="team-a-dev",
    )

    with pytest.raises(
        ResourcePermissionDeniedError,
    ):
        prepare_restart_action(
            session=db_session,
            current_user=user,
            deployment_name="api",
            namespace="team-b-dev",
            kubernetes_write_enabled=True,
            kubernetes_restart_allowed_namespaces=("team-a-dev,team-b-dev"),
            kubernetes_restart_allowed_deployments="api",
            kubernetes_config_mode="mock",
            kubernetes_context="",
        )
