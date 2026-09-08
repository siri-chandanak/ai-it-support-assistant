from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from ai_it_support_assistant.main import app
from ai_it_support_assistant.schemas.rag import (
    RAGResponse,
    RAGSource,
)
from ai_it_support_assistant.services.llm_service import (
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    generate_grounded_answer,
    get_openai_client,
)

client = TestClient(app)


def test_generate_grounded_answer_returns_output_text() -> None:
    mock_client = MagicMock()

    mock_client.responses.create.return_value = SimpleNamespace(
        output_text=(
            '{"answer":"Restart the VPN client.",'
            '"cited_source_numbers":[1],'
            '"insufficient_context":false}'
        )
    )

    with patch(
        "ai_it_support_assistant.services.llm_service.get_openai_client",
        return_value=mock_client,
    ):
        result = generate_grounded_answer(
            question="How do I fix VPN?",
            context="[Source 1]\nRestart the VPN client.",
            api_key="test-key",
            model_name="test-model",
            timeout_seconds=10.0,
            max_retries=3,
        )

    assert result.answer == "Restart the VPN client."
    assert result.cited_source_numbers == [1]
    assert result.insufficient_context is False

    mock_client.responses.create.assert_called_once()


def test_openai_client_requires_api_key() -> None:
    get_openai_client.cache_clear()

    with pytest.raises(
        LLMError,
        match="OpenAI API key is not configured",
    ):
        get_openai_client("", 10.0, 3)


def test_rag_endpoint_returns_answer(reader_auth_override: None) -> None:
    fake_response = RAGResponse(
        question="How do I fix VPN?",
        answer="Restart the VPN client.",
        insufficient_context=False,
        sources=[
            RAGSource(
                chunk_id="doc-1:0",
                document_id="doc-1",
                chunk_index=0,
                score=0.9,
            )
        ],
        retrieved_chunks=[],
    )

    with patch(
        "ai_it_support_assistant.api.routes.rag.answer_question",
        return_value=fake_response,
    ):
        response = client.post(
            "/api/v1/rag/answer",
            json={"question": "How do I fix VPN?"},
        )

    assert response.status_code == 200

    body = response.json()

    assert body["answer"] == "Restart the VPN client."
    assert body["insufficient_context"] is False
    assert len(body["sources"]) == 1


def test_generate_grounded_answer_rejects_invalid_output() -> None:
    mock_client = MagicMock()

    mock_client.responses.create.return_value = SimpleNamespace(output_text='{"something":"wrong"}')

    with patch(
        "ai_it_support_assistant.services.llm_service.get_openai_client",
        return_value=mock_client,
    ):
        with pytest.raises(
            LLMError,
            match="invalid structured output",
        ):
            generate_grounded_answer(
                question="How do I fix VPN?",
                context="[Source 1]\nRestart VPN.",
                api_key="test-key",
                model_name="test-model",
                timeout_seconds=10.0,
                max_retries=3,
            )


def test_openai_client_uses_resilience_settings() -> None:
    get_openai_client.cache_clear()

    with patch("ai_it_support_assistant.services.llm_service.OpenAI") as mock_openai:
        get_openai_client(
            "test-key",
            25.0,
            3,
        )

    mock_openai.assert_called_once_with(
        api_key="test-key",
        timeout=25.0,
        max_retries=3,
    )


def test_rag_endpoint_returns_504_for_llm_timeout(reader_auth_override: None) -> None:
    with patch(
        "ai_it_support_assistant.api.routes.rag.answer_question",
        side_effect=LLMTimeoutError("LLM timed out."),
    ):
        response = client.post(
            "/api/v1/rag/answer",
            json={"question": "How do I fix VPN?"},
        )

    assert response.status_code == 504

    assert response.json() == {"detail": "Answer generation timed out."}


def test_rag_endpoint_handles_llm_rate_limit(reader_auth_override: None) -> None:
    with patch(
        "ai_it_support_assistant.api.routes.rag.answer_question",
        side_effect=LLMRateLimitError("Rate limited."),
    ):
        response = client.post(
            "/api/v1/rag/answer",
            json={"question": "How do I fix VPN?"},
        )

    assert response.status_code == 503
