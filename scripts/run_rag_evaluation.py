import json
from datetime import UTC, datetime
from pathlib import Path

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.evaluation.evaluator import (
    build_evaluation_summary,
    evaluate_case,
    load_evaluation_cases,
)


def main() -> None:
    settings = get_settings()

    cases = load_evaluation_cases(Path("data/evaluation/rag_cases.json"))

    results = [
        evaluate_case(
            case=case,
            settings=settings,
        )
        for case in cases
    ]

    summary = build_evaluation_summary(
        results,
        embedding_model_name=settings.embedding_model_name,
        llm_model=settings.llm_model,
        rag_top_k=settings.rag_top_k,
        rag_score_threshold=settings.rag_score_threshold,
        qdrant_timeout_seconds=settings.qdrant_timeout_seconds,
        qdrant_max_attempts=settings.qdrant_max_attempts,
        openai_timeout_seconds=settings.openai_timeout_seconds,
        openai_max_retries=settings.openai_max_retries,
    )

    output = json.dumps(
        summary.model_dump(),
        indent=2,
    )

    print(output)

    results_directory = Path("data/evaluation/results/")
    results_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    output_path = results_directory / f"rag-evaluation-{timestamp}.json"

    output_path.write_text(
        output,
        encoding="utf-8",
    )

    print(f"\nSaved evaluation report to: {output_path}")


if __name__ == "__main__":
    main()
