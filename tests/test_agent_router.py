from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ai_it_support_assistant.schemas.agent import AgentDecision
from ai_it_support_assistant.services.agent_router_service import (
    AgentRoutingError,
    route_agent_request,
    validate_agent_decision,
)


def test_router_selects_rag() -> None:
    mock_client = MagicMock()

    mock_client.responses.create.return_value = SimpleNamespace(
        output_text=(
            '{"action":"rag",'
            '"service_name":null,'
            '"kubernetes_resource_type":null,'
            '"kubernetes_resource_name":null,'
            '"kubernetes_namespace":null,'
            '"reasoning_summary":"The question asks about a runbook."}'
        )
    )

    with patch(
        ("ai_it_support_assistant.services.agent_router_service.get_openai_client"),
        return_value=mock_client,
    ):
        decision = route_agent_request(
            question="How do I troubleshoot VPN?",
            api_key="test",
            model_name="test",
            timeout_seconds=10,
            max_retries=0,
        )

    assert decision.action == "rag"
    assert decision.service_name is None
    assert decision.kubernetes_resource_type is None
    assert decision.kubernetes_resource_name is None
    assert decision.kubernetes_namespace is None


def test_router_selects_live_status() -> None:
    mock_client = MagicMock()

    mock_client.responses.create.return_value = SimpleNamespace(
        output_text=(
            '{"action":"live_status",'
            '"service_name":"vpn-gateway",'
            '"kubernetes_resource_type":null,'
            '"kubernetes_resource_name":null,'
            '"kubernetes_namespace":null,'
            '"reasoning_summary":"The user asks for live health."}'
        )
    )

    with patch(
        ("ai_it_support_assistant.services.agent_router_service.get_openai_client"),
        return_value=mock_client,
    ):
        decision = route_agent_request(
            question="Is vpn-gateway healthy right now?",
            api_key="test",
            model_name="test",
            timeout_seconds=10,
            max_retries=0,
        )

    assert decision.action == "live_status"
    assert decision.service_name == "vpn-gateway"
    assert decision.kubernetes_resource_type is None
    assert decision.kubernetes_resource_name is None
    assert decision.kubernetes_namespace is None


def test_router_rejects_live_status_without_service_name() -> None:
    mock_client = MagicMock()

    mock_client.responses.create.return_value = SimpleNamespace(
        output_text=(
            '{"action":"live_status",'
            '"service_name":null,'
            '"reasoning_summary":"Live health question."}'
        )
    )

    with patch(
        ("ai_it_support_assistant.services.agent_router_service.get_openai_client"),
        return_value=mock_client,
    ):
        with pytest.raises(AgentRoutingError):
            route_agent_request(
                question="Is the service healthy?",
                api_key="test",
                model_name="test",
                timeout_seconds=10,
                max_retries=0,
            )


def test_validate_rag_decision() -> None:
    decision = AgentDecision(
        action="rag",
        service_name=None,
        kubernetes_resource_type=None,
        kubernetes_resource_name=None,
        kubernetes_namespace=None,
        reasoning_summary="The user asks for documented troubleshooting guidance.",
    )

    validate_agent_decision(decision)


def test_rag_rejects_tool_arguments() -> None:
    decision = AgentDecision(
        action="rag",
        service_name=None,
        kubernetes_resource_type="deployment",
        kubernetes_resource_name="payment-api",
        kubernetes_namespace="ai-it-support-test",
        reasoning_summary="Invalid mixed routing decision.",
    )

    with pytest.raises(
        AgentRoutingError,
        match="rag must not contain tool arguments",
    ):
        validate_agent_decision(decision)


def test_validate_live_status_decision() -> None:
    decision = AgentDecision(
        action="live_status",
        service_name="vpn-gateway",
        kubernetes_resource_type=None,
        kubernetes_resource_name=None,
        kubernetes_namespace=None,
        reasoning_summary="The user asks for current service health.",
    )

    validate_agent_decision(decision)


def test_live_status_requires_service_name() -> None:
    decision = AgentDecision(
        action="live_status",
        service_name=None,
        kubernetes_resource_type=None,
        kubernetes_resource_name=None,
        kubernetes_namespace=None,
        reasoning_summary="Service health requested.",
    )

    with pytest.raises(
        AgentRoutingError,
        match=r"live_status requires a service name\.",
    ):
        validate_agent_decision(decision)


def test_live_status_rejects_kubernetes_arguments() -> None:
    decision = AgentDecision(
        action="live_status",
        service_name="vpn-gateway",
        kubernetes_resource_type="deployment",
        kubernetes_resource_name="vpn-gateway",
        kubernetes_namespace="ai-it-support-test",
        reasoning_summary="Invalid mixed routing decision.",
    )

    with pytest.raises(
        AgentRoutingError,
        match="live_status cannot contain Kubernetes arguments",
    ):
        validate_agent_decision(decision)


def test_validate_kubernetes_state_decision() -> None:
    decision = AgentDecision(
        action="kubernetes_state",
        service_name=None,
        kubernetes_resource_type="deployment",
        kubernetes_resource_name="demo-api",
        kubernetes_namespace="ai-it-support-test",
        reasoning_summary="The user asks for current Deployment state.",
    )

    validate_agent_decision(decision)


def test_kubernetes_state_requires_resource_type() -> None:
    decision = AgentDecision(
        action="kubernetes_state",
        service_name=None,
        kubernetes_resource_type=None,
        kubernetes_resource_name="demo-api",
        kubernetes_namespace="ai-it-support-test",
        reasoning_summary="Current Kubernetes state requested.",
    )

    with pytest.raises(
        AgentRoutingError,
        match="kubernetes_state requires resource type",
    ):
        validate_agent_decision(decision)


def test_kubernetes_state_requires_resource_name() -> None:
    decision = AgentDecision(
        action="kubernetes_state",
        service_name=None,
        kubernetes_resource_type="deployment",
        kubernetes_resource_name=None,
        kubernetes_namespace="ai-it-support-test",
        reasoning_summary="Current Kubernetes state requested.",
    )

    with pytest.raises(
        AgentRoutingError,
        match="kubernetes_state requires resource name",
    ):
        validate_agent_decision(decision)


def test_kubernetes_state_rejects_service_name() -> None:
    decision = AgentDecision(
        action="kubernetes_state",
        service_name="payment-api",
        kubernetes_resource_type="deployment",
        kubernetes_resource_name="payment-api",
        kubernetes_namespace="ai-it-support-test",
        reasoning_summary="Invalid mixed routing decision.",
    )

    with pytest.raises(
        AgentRoutingError,
        match="kubernetes_state cannot contain service_name",
    ):
        validate_agent_decision(decision)


def test_kubernetes_resource_type_rejects_secret() -> None:
    with pytest.raises(ValueError):
        AgentDecision(
            action="kubernetes_state",
            service_name=None,
            kubernetes_resource_type="secret",
            kubernetes_resource_name="my-secret",
            kubernetes_namespace="ai-it-support-test",
            reasoning_summary="Testing Kubernetes resource allowlist.",
        )


def test_router_selects_kubernetes_state() -> None:
    mock_client = MagicMock()

    mock_client.responses.create.return_value = SimpleNamespace(
        output_text=(
            '{"action":"kubernetes_state",'
            '"service_name":null,'
            '"kubernetes_resource_type":"deployment",'
            '"kubernetes_resource_name":"demo-api",'
            '"kubernetes_namespace":"ai-it-support-test",'
            '"reasoning_summary":'
            '"The user asks for the current Deployment state."}'
        )
    )

    with patch(
        ("ai_it_support_assistant.services.agent_router_service.get_openai_client"),
        return_value=mock_client,
    ):
        decision = route_agent_request(
            question=(
                "How many ready replicas does demo-api currently have in ai-it-support-test?"
            ),
            api_key="test-key",
            model_name="test-model",
            timeout_seconds=5.0,
            max_retries=1,
        )

    assert decision.action == "kubernetes_state"
    assert decision.service_name is None
    assert decision.kubernetes_resource_type == "deployment"
    assert decision.kubernetes_resource_name == "demo-api"
    assert decision.kubernetes_namespace == "ai-it-support-test"


def test_router_rejects_kubernetes_state_without_resource_name() -> None:
    mock_client = MagicMock()

    mock_client.responses.create.return_value = SimpleNamespace(
        output_text=(
            '{"action":"kubernetes_state",'
            '"service_name":null,'
            '"kubernetes_resource_type":"deployment",'
            '"kubernetes_resource_name":null,'
            '"kubernetes_namespace":"ai-it-support-test",'
            '"reasoning_summary":'
            '"The user asks for current Deployment state."}'
        )
    )

    with patch(
        ("ai_it_support_assistant.services.agent_router_service.get_openai_client"),
        return_value=mock_client,
    ):
        with pytest.raises(
            AgentRoutingError,
            match="kubernetes_state requires resource name",
        ):
            route_agent_request(
                question=("What is the current demo-api Deployment state?"),
                api_key="test-key",
                model_name="test-model",
                timeout_seconds=5.0,
                max_retries=1,
            )
