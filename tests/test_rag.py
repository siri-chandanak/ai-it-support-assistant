from unittest.mock import patch

from ai_it_support_assistant.schemas.retrieval import RetrievedChunk
from ai_it_support_assistant.services.rag_service import answer_question, build_context


def test_build_context_contains_retrieved_chunks() -> None:
    chunks = [
        RetrievedChunk(
            chunk_id="doc-1:0",
            document_id="doc-1",
            chunk_index=0,
            text="Restart the VPN client.",
            score=0.91,
        ),
        RetrievedChunk(
            chunk_id="doc-1:1",
            document_id="doc-1",
            chunk_index=1,
            text="Clear cached credentials.",
            score=0.84,
        ),
    ]

    context = build_context(chunks)

    assert "[Source 1]" in context
    assert "Restart the VPN client." in context

    assert "[Source 2]" in context
    assert "Clear cached credentials." in context

    assert "doc-1:0" in context
    assert "doc-1:1" in context


def test_build_context_returns_empty_string_for_no_chunks() -> None:
    assert build_context([]) == ""


def test_answer_question_generates_grounded_response() -> None:
    retrieved = [
        RetrievedChunk(
            chunk_id="doc-1:0",
            document_id="doc-1",
            chunk_index=0,
            text="Restart the VPN client.",
            score=0.91,
        )
    ]

    with (
        patch(
            "ai_it_support_assistant.services.rag_service.retrieve_chunks",
            return_value=retrieved,
        ),
        patch(
            "ai_it_support_assistant.services.rag_service.generate_grounded_answer",
            return_value="Restart the VPN client.",
        ),
    ):
        response = answer_question(
            question="How do I fix the VPN?",
            top_k=3,
            score_threshold=0.4,
            embedding_model_name="test-model",
            qdrant_url="http://test-qdrant:6333",
            collection_name="test_chunks",
            openai_api_key="test-key",
            llm_model="test-llm",
        )

    assert response.question == "How do I fix the VPN?"
    assert response.answer == "Restart the VPN client."

    assert len(response.sources) == 1
    assert response.sources[0].chunk_id == "doc-1:0"

    assert len(response.retrieved_chunks) == 1


def test_answer_question_abstains_when_no_chunks_found() -> None:
    with patch(
        "ai_it_support_assistant.services.rag_service.retrieve_chunks",
        return_value=[],
    ):
        response = answer_question(
            question="What is the production database password?",
            top_k=3,
            score_threshold=0.4,
            embedding_model_name="test-model",
            qdrant_url="http://test",
            collection_name="test",
            openai_api_key="test-key",
            llm_model="test-llm",
        )

    assert response.sources == []
    assert response.retrieved_chunks == []

    assert "couldn't find sufficiently relevant information" in response.answer


def test_llm_is_not_called_when_no_chunks_found() -> None:
    with (
        patch(
            "ai_it_support_assistant.services.rag_service.retrieve_chunks",
            return_value=[],
        ),
        patch(
            "ai_it_support_assistant.services.rag_service.generate_grounded_answer",
        ) as mock_generate,
    ):
        answer_question(
            question="Unknown question",
            top_k=3,
            score_threshold=0.4,
            embedding_model_name="test-model",
            qdrant_url="http://test",
            collection_name="test",
            openai_api_key="test-key",
            llm_model="test-llm",
        )

    mock_generate.assert_not_called()


def test_answer_question_abstains_below_threshold() -> None:
    retrieved = [
        RetrievedChunk(
            chunk_id="doc-1:0",
            document_id="doc-1",
            chunk_index=0,
            text="Printer setup instructions.",
            score=0.22,
        )
    ]

    with (
        patch(
            "ai_it_support_assistant.services.rag_service.retrieve_chunks",
            return_value=retrieved,
        ),
        patch(
            "ai_it_support_assistant.services.rag_service.generate_grounded_answer",
        ) as mock_generate,
    ):
        response = answer_question(
            question="What is the database failover process?",
            top_k=3,
            score_threshold=0.4,
            embedding_model_name="test-model",
            qdrant_url="http://test",
            collection_name="test",
            openai_api_key="test-key",
            llm_model="test-model",
        )

    assert response.sources == []
    assert "couldn't find sufficiently relevant" in response.answer

    mock_generate.assert_not_called()
