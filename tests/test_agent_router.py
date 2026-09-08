from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ai_it_support_assistant.services.agent_router_service import (
    AgentRoutingError,
    route_agent_request,
)


def test_router_selects_rag() -> None:
    mock_client = MagicMock()

    mock_client.responses.create.return_value = SimpleNamespace(
        output_text=(
            '{"action":"rag",'
            '"service_name":null,'
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


def test_router_selects_live_status() -> None:
    mock_client = MagicMock()

    mock_client.responses.create.return_value = SimpleNamespace(
        output_text=(
            '{"action":"live_status",'
            '"service_name":"vpn-gateway",'
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
