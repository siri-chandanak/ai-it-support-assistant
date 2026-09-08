from unittest.mock import patch
from uuid import UUID

import pytest

from ai_it_support_assistant.schemas.agent import (
    AgentDecision,
)
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.schemas.rag import RAGResponse
from ai_it_support_assistant.schemas.tools import (
    ServiceStatus,
)
from ai_it_support_assistant.services.agent_service import (
    handle_agent_request,
)
from ai_it_support_assistant.services.tool_authorization_service import (
    ToolAuthorizationError,
)


def _agent_kwargs() -> dict:
    return {
        "embedding_model_name": "test-embedding",
        "qdrant_url": "http://localhost:6333",
        "collection_name": "document_chunks",
        "qdrant_timeout_seconds": 5.0,
        "qdrant_max_attempts": 1,
        "rag_top_k": 3,
        "rag_score_threshold": 0.5,
        "openai_api_key": "test",
        "llm_model": "test-model",
        "openai_timeout_seconds": 10.0,
        "openai_max_retries": 0,
        "embedding_cache_enabled": False,
        "retrieval_cache_enabled": False,
    }


def test_agent_executes_only_rag_path() -> None:
    user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        username="reader",
        roles=["reader"],
    )

    decision = AgentDecision(
        action="rag",
        service_name=None,
        reasoning_summary="Documentation question.",
    )

    rag_response = RAGResponse(
        question="How do I troubleshoot VPN?",
        answer="Restart the VPN client.",
        sources=[],
        retrieved_chunks=[],
        insufficient_context=False,
    )

    with (
        patch(
            "ai_it_support_assistant.services.agent_service.route_agent_request",
            return_value=decision,
        ),
        patch(
            "ai_it_support_assistant.services.agent_service.answer_question",
            return_value=rag_response,
        ) as mock_rag,
        patch(
            "ai_it_support_assistant.services.agent_service.get_live_service_status"
        ) as mock_live,
    ):
        result = handle_agent_request(
            question="How do I troubleshoot VPN?",
            current_user=user,
            **_agent_kwargs(),
        )

    assert result.action == "rag"
    assert result.answer == "Restart the VPN client."

    mock_rag.assert_called_once()
    mock_live.assert_not_called()


def test_agent_executes_only_live_status_path() -> None:
    user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000002"),
        username="support",
        roles=["it_support"],
    )

    decision = AgentDecision(
        action="live_status",
        service_name="vpn-gateway",
        reasoning_summary="Live status question.",
    )

    service_status = ServiceStatus(
        service_name="vpn-gateway",
        status="degraded",
        message="Authentication latency is elevated.",
    )

    with (
        patch(
            "ai_it_support_assistant.services.agent_service.route_agent_request",
            return_value=decision,
        ),
        patch("ai_it_support_assistant.services.agent_service.answer_question") as mock_rag,
        patch(
            "ai_it_support_assistant.services.agent_service.get_live_service_status",
            return_value=service_status,
        ) as mock_live,
    ):
        result = handle_agent_request(
            question="Is vpn-gateway healthy right now?",
            current_user=user,
            **_agent_kwargs(),
        )

    assert result.action == "live_status"
    assert "vpn-gateway is degraded" in result.answer

    mock_live.assert_called_once()
    mock_rag.assert_not_called()


def test_authorization_happens_before_live_tool_execution() -> None:
    user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000003"),
        username="reader",
        roles=["reader"],
    )

    decision = AgentDecision(
        action="live_status",
        service_name="vpn-gateway",
        reasoning_summary="Live status question.",
    )

    with (
        patch(
            "ai_it_support_assistant.services.agent_service.route_agent_request",
            return_value=decision,
        ),
        patch(
            "ai_it_support_assistant.services.agent_service.get_live_service_status"
        ) as mock_live,
    ):
        with pytest.raises(ToolAuthorizationError):
            handle_agent_request(
                question="Is vpn-gateway healthy right now?",
                current_user=user,
                **_agent_kwargs(),
            )

    mock_live.assert_not_called()
