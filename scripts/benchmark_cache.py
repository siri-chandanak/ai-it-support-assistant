from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from uuid import uuid4

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.services.rag_service import (
    answer_question,
)

RESULTS_PATH = Path("performance/results/cache-benchmark.json")

ITERATIONS = 15

BASE_QUESTION = "What should a user do if VPN login fails after a password change?"


def percentile(
    values: list[float],
    percentile_value: float,
) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)

    index = int((len(ordered) - 1) * percentile_value)

    return ordered[index]


def call_rag(
    *,
    question: str,
    embedding_cache_enabled: bool,
    retrieval_cache_enabled: bool,
) -> None:
    settings = get_settings()

    answer_question(
        question=question,
        top_k=settings.rag_top_k,
        score_threshold=settings.rag_score_threshold,
        embedding_model_name=settings.embedding_model_name,
        qdrant_url=settings.qdrant_url,
        collection_name=settings.qdrant_collection_name,
        qdrant_timeout_seconds=settings.qdrant_timeout_seconds,
        qdrant_max_attempts=settings.qdrant_max_attempts,
        user_roles=["reader"],
        embedding_cache_enabled=(embedding_cache_enabled),
        retrieval_cache_enabled=(retrieval_cache_enabled),
        openai_api_key=settings.openai_api_key,
        llm_model=settings.llm_model,
        openai_timeout_seconds=settings.openai_timeout_seconds,
        openai_max_retries=settings.openai_max_retries,
    )


def benchmark_warm() -> dict[str, object]:
    timings_ms: list[float] = []

    # Prime caches.
    call_rag(
        question=BASE_QUESTION,
        embedding_cache_enabled=True,
        retrieval_cache_enabled=True,
    )

    for _ in range(ITERATIONS):
        started = time.perf_counter()

        call_rag(
            question=BASE_QUESTION,
            embedding_cache_enabled=True,
            retrieval_cache_enabled=True,
        )

        timings_ms.append((time.perf_counter() - started) * 1000)

    return summarize(
        "warm",
        timings_ms,
    )


def benchmark_coldish() -> dict[str, object]:
    timings_ms: list[float] = []

    for index in range(ITERATIONS):
        question = f"{BASE_QUESTION} Benchmark variation {index}-{uuid4().hex[:8]}"

        started = time.perf_counter()

        call_rag(
            question=question,
            embedding_cache_enabled=False,
            retrieval_cache_enabled=False,
        )

        timings_ms.append((time.perf_counter() - started) * 1000)

    return summarize(
        "cold-ish",
        timings_ms,
    )


def summarize(
    scenario: str,
    timings_ms: list[float],
) -> dict[str, object]:
    return {
        "scenario": scenario,
        "iterations": len(timings_ms),
        "average_ms": round(
            statistics.mean(timings_ms),
            2,
        ),
        "p50_ms": round(
            percentile(timings_ms, 0.50),
            2,
        ),
        "p95_ms": round(
            percentile(timings_ms, 0.95),
            2,
        ),
        "p99_ms": round(
            percentile(timings_ms, 0.99),
            2,
        ),
    }


def main() -> None:
    RESULTS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    warm = benchmark_warm()
    cold = benchmark_coldish()

    print(warm)
    print(cold)

    RESULTS_PATH.write_text(
        json.dumps(
            {
                "warm": warm,
                "cold": cold,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
