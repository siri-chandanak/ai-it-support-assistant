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
    generate_grounded_answer,
    get_openai_client,
)

client = TestClient(app)


def test_generate_grounded_answer_returns_output_text() -> None:
    mock_client = MagicMock()

    mock_client.responses.create.return_value = SimpleNamespace(
        output_text="Restart the VPN client."
    )

    with patch(
        "ai_it_support_assistant.services.llm_service.get_openai_client",
        return_value=mock_client,
    ):
        answer = generate_grounded_answer(
            question="How do I fix VPN?",
            context="Restart the VPN client.",
            api_key="test-key",
            model_name="test-model",
        )

    assert answer == "Restart the VPN client."

    mock_client.responses.create.assert_called_once()


def test_openai_client_requires_api_key() -> None:
    get_openai_client.cache_clear()

    with pytest.raises(
        LLMError,
        match="OpenAI API key is not configured",
    ):
        get_openai_client("")


def test_rag_endpoint_returns_answer() -> None:
    fake_response = RAGResponse(
        question="How do I fix VPN?",
        answer="Restart the VPN client.",
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
    assert len(body["sources"]) == 1
