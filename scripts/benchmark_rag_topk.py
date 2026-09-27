from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, median
from time import perf_counter

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.services.rag_service import (
    answer_question,
)

TOP_K_VALUES = [1, 2, 3]

ITERATIONS = 10

QUESTION = "What should a user do when VPN login fails?"

RESULT_FILE = Path("performance/results/rag-topk-benchmark.json")


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
    top_k: int,
):
    return answer_question(
        question=QUESTION,
        top_k=top_k,
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


def benchmark_top_k(
    *,
    settings,
    top_k: int,
) -> dict:
    timings_ms: list[float] = []

    error_count = 0
    insufficient_count = 0

    source_counts: list[int] = []

    print()
    print(f"Benchmarking top_k={top_k}")

    #
    # Warm-up.
    #
    started = perf_counter()

    try:
        response = run_rag(
            settings=settings,
            top_k=top_k,
        )

        warmup_ms = (perf_counter() - started) * 1000

        print(f"Warm-up: {warmup_ms:.2f} ms")

        print(f"Warm-up sources: {len(response.sources)}")

    except Exception as exc:
        warmup_ms = (perf_counter() - started) * 1000

        print(f"Warm-up failed: {type(exc).__name__}: {exc}")

    #
    # Measured requests.
    #
    for iteration in range(
        1,
        ITERATIONS + 1,
    ):
        started = perf_counter()

        try:
            response = run_rag(
                settings=settings,
                top_k=top_k,
            )

            elapsed_ms = (perf_counter() - started) * 1000

            timings_ms.append(elapsed_ms)

            source_count = len(response.sources)

            source_counts.append(source_count)

            if response.insufficient_context:
                insufficient_count += 1

            print(
                f"{iteration:02d}: "
                f"{elapsed_ms:.2f} ms "
                f"sources={source_count} "
                f"insufficient="
                f"{response.insufficient_context}"
            )

        except Exception as exc:
            elapsed_ms = (perf_counter() - started) * 1000

            timings_ms.append(elapsed_ms)

            error_count += 1

            print(f"{iteration:02d}: {elapsed_ms:.2f} ms ERROR {type(exc).__name__}: {exc}")

    return {
        "top_k": top_k,
        "iterations": ITERATIONS,
        "warmup_ms": round(
            warmup_ms,
            2,
        ),
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
        "error_count": error_count,
        "insufficient_context_count": (insufficient_count),
        "average_source_count": (
            round(
                mean(source_counts),
                2,
            )
            if source_counts
            else 0.0
        ),
    }


def main() -> None:
    settings = get_settings()

    results: list[dict] = []

    print()
    print("Full RAG top_k Benchmark")
    print("------------------------")
    print(f"Model: {settings.llm_model}")
    print(f"Iterations/top_k: {ITERATIONS}")

    for top_k in TOP_K_VALUES:
        result = benchmark_top_k(
            settings=settings,
            top_k=top_k,
        )

        results.append(result)

    RESULT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = {
        "question": QUESTION,
        "model": settings.llm_model,
        "results": results,
    }

    RESULT_FILE.write_text(
        json.dumps(
            output,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("Comparison")
    print("----------")

    for result in results:
        print(
            f"top_k="
            f"{result['top_k']} | "
            f"p50="
            f"{result['p50_ms']:.2f} ms | "
            f"p95="
            f"{result['p95_ms']:.2f} ms | "
            f"p99="
            f"{result['p99_ms']:.2f} ms | "
            f"insufficient="
            f"{result['insufficient_context_count']} | "
            f"errors="
            f"{result['error_count']} | "
            f"avg_sources="
            f"{result['average_source_count']:.2f}"
        )

    print()
    print(f"Saved benchmark: {RESULT_FILE}")


if __name__ == "__main__":
    main()
