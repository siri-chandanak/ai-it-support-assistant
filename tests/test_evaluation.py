from types import SimpleNamespace
from unittest.mock import patch

from ai_it_support_assistant.evaluation.evaluator import (
    contains_expected_keywords,
    evaluate_answer_behavior,
    evaluate_case,
    has_expected_document,
)
from ai_it_support_assistant.evaluation.models import (
    EvaluationCase,
)
from ai_it_support_assistant.schemas.rag import (
    RAGResponse,
    RAGSource,
)
from ai_it_support_assistant.schemas.retrieval import RetrievedChunk


def test_answer_behavior_for_answerable_case() -> None:
    expected, actual, correct = evaluate_answer_behavior(
        should_answer=True,
        insufficient_context=False,
    )

    assert expected == "answer"
    assert actual == "answer"
    assert correct is True


def test_answer_behavior_for_abstention() -> None:
    expected, actual, correct = evaluate_answer_behavior(
        should_answer=False,
        insufficient_context=True,
    )

    assert expected == "abstain"
    assert actual == "abstain"
    assert correct is True


def test_expected_keywords_match_case_insensitively() -> None:
    result = contains_expected_keywords(
        answer=("Restart the VPN and clear cached credentials."),
        expected_keywords=[
            "restart",
            "CREDENTIALS",
        ],
    )

    assert result is True


def test_missing_expected_keyword_fails() -> None:
    result = contains_expected_keywords(
        answer="Restart the VPN.",
        expected_keywords=[
            "restart",
            "credentials",
        ],
    )

    assert result is False


def test_expected_document_is_retrieved() -> None:
    chunks = [
        RetrievedChunk(
            chunk_id="vpn-doc:0",
            document_id="vpn-doc",
            chunk_index=0,
            text="VPN instructions",
            score=0.9,
        )
    ]

    assert (
        has_expected_document(
            chunks=chunks,
            expected_document_ids=["vpn-doc"],
        )
        is True
    )


def test_expected_document_is_missing() -> None:
    chunks = [
        RetrievedChunk(
            chunk_id="printer-doc:0",
            document_id="printer-doc",
            chunk_index=0,
            text="Printer instructions",
            score=0.8,
        )
    ]

    assert (
        has_expected_document(
            chunks=chunks,
            expected_document_ids=["vpn-doc"],
        )
        is False
    )


def test_evaluate_case_for_successful_answer() -> None:
    case = EvaluationCase(
        case_id="vpn-001",
        question="How do I fix VPN login failure?",
        should_answer=True,
        expected_document_ids=["vpn-doc"],
        expected_keywords=["restart", "credentials"],
    )

    fake_response = RAGResponse(
        question="How do I fix VPN login failure?",
        answer=("Restart the VPN client and clear cached credentials."),
        insufficient_context=False,
        sources=[
            RAGSource(
                citation_number=1,
                document_id="vpn-doc",
                chunk_id="vpn-doc:0",
                chunk_index=0,
                score=0.91,
            )
        ],
        retrieved_chunks=[
            RetrievedChunk(
                chunk_id="vpn-doc:0",
                document_id="vpn-doc",
                chunk_index=0,
                text="Restart the VPN client and clear cached credentials.",
                score=0.91,
            )
        ],
    )

    settings = SimpleNamespace(
        rag_top_k=3,
        rag_score_threshold=0.4,
        embedding_model_name=("sentence-transformers/all-MiniLM-L6-v2"),
        qdrant_url="http://localhost:6333",
        qdrant_collection_name="document_chunks",
        openai_api_key="fake-key",
        llm_model="fake-model",
    )

    with patch(
        "ai_it_support_assistant.evaluation.evaluator.answer_question",
        return_value=fake_response,
    ):
        result = evaluate_case(
            case=case,
            settings=settings,
        )

    assert result.retrieval_hit is True
    assert result.behavior_correct is True
    assert result.citation_valid is True
    assert result.keyword_match is True
    assert result.passed is True


def test_evaluate_case_for_correct_abstention() -> None:
    case = EvaluationCase(
        case_id="unknown-001",
        question="What is today's cafeteria menu?",
        should_answer=False,
        expected_document_ids=[],
        expected_keywords=[],
    )

    fake_response = RAGResponse(
        question="What is today's cafeteria menu?",
        answer="I do not have enough context to answer that.",
        insufficient_context=True,
        sources=[],
        retrieved_chunks=[],
    )

    settings = SimpleNamespace(
        rag_top_k=3,
        rag_score_threshold=0.4,
        embedding_model_name=("sentence-transformers/all-MiniLM-L6-v2"),
        qdrant_url="http://localhost:6333",
        qdrant_collection_name="document_chunks",
        openai_api_key="fake-key",
        llm_model="fake-model",
    )

    with patch(
        "ai_it_support_assistant.evaluation.evaluator.answer_question",
        return_value=fake_response,
    ):
        result = evaluate_case(
            case=case,
            settings=settings,
        )

    assert result.retrieval_hit is True
    assert result.expected_answer_behavior == "abstain"
    assert result.actual_answer_behavior == "abstain"
    assert result.behavior_correct is True
    assert result.citation_valid is True
    assert result.keyword_match is True
    assert result.passed is True
