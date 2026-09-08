import json
from pathlib import Path

from ai_it_support_assistant.core.config import Settings
from ai_it_support_assistant.evaluation.evaluator import (
    evaluate_answer_behavior,
)
from ai_it_support_assistant.evaluation.models import (
    AuthorizationEvaluationCase,
    AuthorizationEvaluationResult,
    AuthorizationEvaluationSummary,
)
from ai_it_support_assistant.schemas.rag import (
    RAGSource,
)
from ai_it_support_assistant.schemas.retrieval import (
    RetrievedChunk,
)
from ai_it_support_assistant.services.rag_service import (
    answer_question,
)


def contains_forbidden_citations(
    *,
    sources: list[RAGSource],
    forbidden_document_ids: list[str],
) -> bool:
    if not forbidden_document_ids:
        return False

    forbidden = set(forbidden_document_ids)

    return any(source.document_id in forbidden for source in sources)


def contains_forbidden_documents(
    *,
    chunks: list[RetrievedChunk],
    forbidden_document_ids: list[str],
) -> bool:
    if not forbidden_document_ids:
        return False

    forbidden = set(forbidden_document_ids)

    return any(chunk.document_id in forbidden for chunk in chunks)


def contains_forbidden_text(
    *,
    answer: str,
    forbidden_fragments: list[str],
) -> bool:
    normalized_answer = answer.lower()

    return any(fragment.lower() in normalized_answer for fragment in forbidden_fragments)


def contains_expected_allowed_document(
    *,
    chunks: list[RetrievedChunk],
    expected_document_ids: list[str],
) -> bool:
    if not expected_document_ids:
        return True

    retrieved_ids = {chunk.document_id for chunk in chunks}

    return any(document_id in retrieved_ids for document_id in expected_document_ids)


def evaluate_authorization_case(
    *,
    case: AuthorizationEvaluationCase,
    settings: Settings,
) -> AuthorizationEvaluationResult:
    response = answer_question(
        question=case.question,
        top_k=settings.rag_top_k,
        score_threshold=(settings.rag_score_threshold),
        embedding_model_name=(settings.embedding_model_name),
        embedding_cache_enabled=(settings.embedding_cache_enabled),
        retrieval_cache_enabled=(settings.retrieval_cache_enabled),
        qdrant_url=settings.qdrant_url,
        collection_name=(settings.qdrant_collection_name),
        openai_api_key=settings.openai_api_key,
        llm_model=settings.llm_model,
        qdrant_timeout_seconds=(settings.qdrant_timeout_seconds),
        qdrant_max_attempts=(settings.qdrant_max_attempts),
        openai_timeout_seconds=settings.openai_timeout_seconds,
        openai_max_retries=settings.openai_max_retries,
        user_roles=case.user_roles,
    )

    if case.case_id in {
        "it-support-restricted-001",
        "admin-restricted-001",
    }:
        print()
        print("=" * 80)
        print(f"CASE: {case.case_id}")
        print(f"QUESTION: {case.question}")
        print(f"ROLES: {case.user_roles}")
        print(f"INSUFFICIENT_CONTEXT: {response.insufficient_context}")
        print(f"ANSWER: {response.answer}")

        print("RETRIEVED:")
        for chunk in response.retrieved_chunks:
            print(
                {
                    "document_id": chunk.document_id,
                    "chunk_id": chunk.chunk_id,
                    "score": chunk.score,
                    "text": chunk.text,
                }
            )

        print("SOURCES:")
        for source in response.sources:
            print(
                {
                    "document_id": source.document_id,
                    "chunk_id": source.chunk_id,
                    "score": source.score,
                }
            )

        print("=" * 80)

    unauthorized_document_leak = contains_forbidden_documents(
        chunks=response.retrieved_chunks,
        forbidden_document_ids=(case.forbidden_document_ids),
    )

    citation_leak = contains_forbidden_citations(
        sources=response.sources,
        forbidden_document_ids=(case.forbidden_document_ids),
    )

    unauthorized_text_leak = contains_forbidden_text(
        answer=response.answer,
        forbidden_fragments=(case.forbidden_text_fragments),
    )

    authorized_retrieval_hit = contains_expected_allowed_document(
        chunks=response.retrieved_chunks,
        expected_document_ids=(case.expected_allowed_document_ids),
    )

    (
        expected_behavior,
        actual_behavior,
        behavior_correct,
    ) = evaluate_answer_behavior(
        should_answer=case.should_answer,
        insufficient_context=(response.insufficient_context),
    )

    passed = all(
        [
            authorized_retrieval_hit,
            not unauthorized_document_leak,
            not citation_leak,
            not unauthorized_text_leak,
            behavior_correct,
        ]
    )

    return AuthorizationEvaluationResult(
        case_id=case.case_id,
        question=case.question,
        user_roles=case.user_roles,
        authorized_retrieval_hit=(authorized_retrieval_hit),
        unauthorized_document_leak=(unauthorized_document_leak),
        unauthorized_text_leak=(unauthorized_text_leak),
        citation_leak=citation_leak,
        expected_behavior=expected_behavior,
        actual_behavior=actual_behavior,
        behavior_correct=behavior_correct,
        passed=passed,
    )


def build_authorization_summary(
    results: list[AuthorizationEvaluationResult],
) -> AuthorizationEvaluationSummary:
    if not results:
        raise ValueError("Cannot summarize empty security evaluation.")

    total = len(results)

    passed = sum(result.passed for result in results)

    document_leaks = sum(result.unauthorized_document_leak for result in results)

    text_leaks = sum(result.unauthorized_text_leak for result in results)

    citation_leaks = sum(result.citation_leak for result in results)

    authorized_hits = sum(result.authorized_retrieval_hit for result in results)

    behavior_correct = sum(result.behavior_correct for result in results)

    return AuthorizationEvaluationSummary(
        total_cases=total,
        passed_cases=passed,
        failed_cases=total - passed,
        pass_rate=passed / total,
        unauthorized_document_leak_count=(document_leaks),
        unauthorized_text_leak_count=(text_leaks),
        citation_leak_count=(citation_leaks),
        authorized_retrieval_rate=(authorized_hits / total),
        behavior_accuracy=(behavior_correct / total),
        results=results,
    )


def load_authorization_cases(
    file_path: Path,
) -> list[AuthorizationEvaluationCase]:
    try:
        raw_data = json.loads(file_path.read_text(encoding="utf-8"))
    except (
        OSError,
        json.JSONDecodeError,
    ) as exc:
        raise ValueError("Unable to load security evaluation dataset.") from exc

    return [AuthorizationEvaluationCase.model_validate(item) for item in raw_data]
