from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, median
from time import perf_counter

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.services.rag_service import (
    answer_question,
)

ITERATIONS = 30

QUESTION = "What should a user do when VPN login fails?"

RESULT_FILE = Path("performance/results/full-rag-benchmark.json")


def percentile(
    values: list[float],
    percentile_value: float,
) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)

    index = round((len(ordered) - 1) * percentile_value)

    return ordered[index]


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

    timings_ms: list[float] = []
    errors: list[str] = []

    print()
    print("Full RAG Benchmark")
    print("------------------")
    print(f"Iterations: {ITERATIONS}")
    print(f"Top K: {settings.rag_top_k}")
    print(f"LLM: {settings.llm_model}")

    print()
    print("Warm-up request...")

    warmup_started = perf_counter()

    try:
        response = run_rag(
            settings=settings,
        )

        warmup_ms = (perf_counter() - warmup_started) * 1000

        print(f"Warm-up latency: {warmup_ms:.2f} ms")
        print(f"Warm-up insufficient_context={response.insufficient_context}")

    except Exception as exc:
        warmup_ms = (perf_counter() - warmup_started) * 1000

        print(f"Warm-up failed after {warmup_ms:.2f} ms: {type(exc).__name__}: {exc}")

    print()
    print("Measured full RAG requests:")

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

            timings_ms.append(elapsed_ms)

            print(
                f"{iteration:02d}: "
                f"{elapsed_ms:.2f} ms "
                f"OK "
                f"insufficient_context="
                f"{response.insufficient_context}"
            )

        except Exception as exc:
            elapsed_ms = (perf_counter() - started) * 1000

            timings_ms.append(elapsed_ms)

            error_message = f"{type(exc).__name__}: {exc}"

            errors.append(error_message)

            print(f"{iteration:02d}: {elapsed_ms:.2f} ms ERROR {error_message}")

    output = {
        "question": QUESTION,
        "iterations": ITERATIONS,
        "warmup_ms": round(
            warmup_ms,
            2,
        ),
        "error_count": len(errors),
        "average_ms": round(
            mean(timings_ms),
            2,
        ),
        "p50_ms": round(
            median(timings_ms),
            2,
        ),
        "p95_ms": round(
            percentile(
                timings_ms,
                0.95,
            ),
            2,
        ),
        "p99_ms": round(
            percentile(
                timings_ms,
                0.99,
            ),
            2,
        ),
        "errors": errors,
    }

    RESULT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    RESULT_FILE.write_text(
        json.dumps(
            output,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("Full RAG Benchmark Summary")
    print("--------------------------")
    print(f"warmup={output['warmup_ms']:.2f} ms")
    print(f"p50={output['p50_ms']:.2f} ms")
    print(f"p95={output['p95_ms']:.2f} ms")
    print(f"p99={output['p99_ms']:.2f} ms")
    print(f"errors={output['error_count']}")

    print()
    print(f"Saved benchmark: {RESULT_FILE}")


if __name__ == "__main__":
    main()
