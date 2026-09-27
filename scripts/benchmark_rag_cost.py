from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter

from prometheus_client import Counter

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.observability.metrics import (
    LLM_ESTIMATED_COST_TOTAL,
    LLM_INPUT_TOKENS,
    LLM_OUTPUT_TOKENS,
)
from ai_it_support_assistant.services.rag_service import (
    answer_question,
)

ITERATIONS = 10

QUESTION = "What should a user do when VPN login fails?"

RESULT_FILE = Path("performance/results/rag-cost-benchmark.json")


def read_counter_value(
    counter: Counter,
    *,
    expected_labels: dict[str, str],
) -> float:
    for metric in counter.collect():
        for sample in metric.samples:
            if not sample.name.endswith("_total"):
                continue

            if sample.labels == expected_labels:
                return float(sample.value)

    return 0.0


def run_rag(
    *,
    settings,
):
    return answer_question(
        question=QUESTION,
        top_k=settings.rag_top_k,
        score_threshold=(settings.rag_score_threshold),
        embedding_model_name=(settings.embedding_model_name),
        embedding_cache_enabled=(settings.embedding_cache_enabled),
        retrieval_cache_enabled=(settings.retrieval_cache_enabled),
        qdrant_url=settings.qdrant_url,
        collection_name=(settings.qdrant_collection_name),
        openai_api_key=(settings.openai_api_key),
        llm_model=settings.llm_model,
        qdrant_timeout_seconds=(settings.qdrant_timeout_seconds),
        qdrant_max_attempts=(settings.qdrant_max_attempts),
        openai_timeout_seconds=(settings.openai_timeout_seconds),
        openai_max_retries=(settings.openai_max_retries),
        user_roles=["admin"],
    )


def main() -> None:
    settings = get_settings()

    labels = {
        "model": settings.llm_model,
        "operation": "rag_answer",
    }

    input_before = read_counter_value(
        LLM_INPUT_TOKENS,
        expected_labels=labels,
    )

    output_before = read_counter_value(
        LLM_OUTPUT_TOKENS,
        expected_labels=labels,
    )

    cost_before = read_counter_value(
        LLM_ESTIMATED_COST_TOTAL,
        expected_labels=labels,
    )

    successes = 0
    errors = 0

    print()
    print("RAG Token / Cost Benchmark")
    print("--------------------------")
    print(f"Model: {settings.llm_model}")
    print(f"Iterations: {ITERATIONS}")

    for iteration in range(
        1,
        ITERATIONS + 1,
    ):
        started = perf_counter()

        try:
            response = run_rag(
                settings=settings,
            )

            elapsed_ms = (perf_counter() - started) * 1000

            successes += 1

            print(f"{iteration:02d}: {elapsed_ms:.2f} ms OK sources={len(response.sources)}")

        except Exception as exc:
            errors += 1

            elapsed_ms = (perf_counter() - started) * 1000

            print(f"{iteration:02d}: {elapsed_ms:.2f} ms ERROR {type(exc).__name__}: {exc}")

    input_after = read_counter_value(
        LLM_INPUT_TOKENS,
        expected_labels=labels,
    )

    output_after = read_counter_value(
        LLM_OUTPUT_TOKENS,
        expected_labels=labels,
    )

    cost_after = read_counter_value(
        LLM_ESTIMATED_COST_TOTAL,
        expected_labels=labels,
    )

    total_input_tokens = input_after - input_before

    total_output_tokens = output_after - output_before

    total_cost = cost_after - cost_before

    if successes > 0:
        average_input_tokens = total_input_tokens / successes

        average_output_tokens = total_output_tokens / successes

        average_cost = total_cost / successes
    else:
        average_input_tokens = 0.0
        average_output_tokens = 0.0
        average_cost = 0.0

    result = {
        "model": settings.llm_model,
        "iterations": ITERATIONS,
        "successes": successes,
        "errors": errors,
        "total_input_tokens": (total_input_tokens),
        "total_output_tokens": (total_output_tokens),
        "average_input_tokens": round(
            average_input_tokens,
            2,
        ),
        "average_output_tokens": round(
            average_output_tokens,
            2,
        ),
        "total_estimated_cost": round(
            total_cost,
            8,
        ),
        "estimated_cost_per_rag_answer": round(
            average_cost,
            8,
        ),
    }

    RESULT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    RESULT_FILE.write_text(
        json.dumps(
            result,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("Token / Cost Summary")
    print("--------------------")
    print(f"avg input tokens....{average_input_tokens:.2f}")
    print(f"avg output tokens...{average_output_tokens:.2f}")
    print(f"cost / RAG answer...${average_cost:.8f}")
    print(f"errors...............{errors}")

    print()
    print(f"Saved benchmark: {RESULT_FILE}")


if __name__ == "__main__":
    main()
