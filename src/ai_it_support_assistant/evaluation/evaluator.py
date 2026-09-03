import json
from pathlib import Path

from ai_it_support_assistant.core.config import Settings
from ai_it_support_assistant.evaluation.models import (
    EvaluationCase,
    EvaluationResult,
    EvaluationSummary,
)
from ai_it_support_assistant.schemas.retrieval import RetrievedChunk
from ai_it_support_assistant.services.rag_service import (
    answer_question,
)


class EvaluationError(Exception):
    pass


def load_evaluation_cases(
    file_path: Path,
) -> list[EvaluationCase]:
    try:
        raw_data = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationError("Unable to load evaluation dataset.") from exc

    try:
        return [EvaluationCase.model_validate(item) for item in raw_data]
    except Exception as exc:
        raise EvaluationError("Evaluation dataset contains invalid data.") from exc


def has_expected_document(
    *,
    chunks: list[RetrievedChunk],
    expected_document_ids: list[str],
) -> bool:
    if not expected_document_ids:
        return True

    retrieved_document_ids = {chunk.document_id for chunk in chunks}

    return any(document_id in retrieved_document_ids for document_id in expected_document_ids)


def evaluate_answer_behavior(
    *,
    should_answer: bool,
    insufficient_context: bool,
) -> tuple[str, str, bool]:
    expected_behavior = "answer" if should_answer else "abstain"

    actual_behavior = "abstain" if insufficient_context else "answer"

    return (
        expected_behavior,
        actual_behavior,
        expected_behavior == actual_behavior,
    )


def contains_expected_keywords(
    *,
    answer: str,
    expected_keywords: list[str],
) -> bool:
    if not expected_keywords:
        return True

    normalized_answer = answer.lower()

    return all(keyword.lower() in normalized_answer for keyword in expected_keywords)


def evaluate_citations(
    *,
    should_answer: bool,
    insufficient_context: bool,
    source_count: int,
) -> bool:
    if insufficient_context:
        return source_count == 0

    if should_answer:
        return source_count > 0

    return True


def evaluate_case(
    *,
    case: EvaluationCase,
    settings: Settings,
) -> EvaluationResult:
    response = answer_question(
        question=case.question,
        top_k=settings.rag_top_k,
        score_threshold=settings.rag_score_threshold,
        embedding_model_name=settings.embedding_model_name,
        qdrant_url=settings.qdrant_url,
        collection_name=settings.qdrant_collection_name,
        openai_api_key=settings.openai_api_key,
        llm_model=settings.llm_model,
    )

    retrieval_hit = has_expected_document(
        chunks=response.retrieved_chunks,
        expected_document_ids=case.expected_document_ids,
    )

    (
        expected_behavior,
        actual_behavior,
        behavior_correct,
    ) = evaluate_answer_behavior(
        should_answer=case.should_answer,
        insufficient_context=response.insufficient_context,
    )

    citation_valid = evaluate_citations(
        should_answer=case.should_answer,
        insufficient_context=response.insufficient_context,
        source_count=len(response.sources),
    )

    keyword_match = contains_expected_keywords(
        answer=response.answer,
        expected_keywords=case.expected_keywords,
    )

    passed = all(
        [
            retrieval_hit,
            behavior_correct,
            citation_valid,
            keyword_match,
        ]
    )

    return EvaluationResult(
        case_id=case.case_id,
        question=case.question,
        retrieval_hit=retrieval_hit,
        expected_answer_behavior=expected_behavior,
        actual_answer_behavior=actual_behavior,
        behavior_correct=behavior_correct,
        citation_valid=citation_valid,
        keyword_match=keyword_match,
        passed=passed,
    )


def build_evaluation_summary(
    results: list[EvaluationResult],
    embedding_model_name: str,
    llm_model: str,
    rag_top_k: int,
    rag_score_threshold: float,
) -> EvaluationSummary:
    if not results:
        raise EvaluationError("Cannot summarize empty evaluation results.")

    total = len(results)

    passed = sum(result.passed for result in results)

    retrieval_hits = sum(result.retrieval_hit for result in results)

    behavior_correct = sum(result.behavior_correct for result in results)

    citation_correct = sum(result.citation_valid for result in results)

    keyword_correct = sum(result.keyword_match for result in results)

    return EvaluationSummary(
        total_cases=total,
        passed_cases=passed,
        failed_cases=total - passed,
        pass_rate=passed / total,
        retrieval_hit_rate=retrieval_hits / total,
        behavior_accuracy=behavior_correct / total,
        citation_accuracy=citation_correct / total,
        keyword_accuracy=keyword_correct / total,
        results=results,
        embedding_model_name=embedding_model_name,
        llm_model=llm_model,
        rag_top_k=rag_top_k,
        rag_score_threshold=rag_score_threshold,
    )
