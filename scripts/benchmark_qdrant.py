from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, median
from time import perf_counter
from typing import Any

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.services.embedding_service import (
    embed_query,
)
from ai_it_support_assistant.services.retrieval_service import (
    build_authorization_filter,
)
from ai_it_support_assistant.services.vector_store_service import (
    get_qdrant_client,
)

TOP_K_VALUES = [3, 5, 10, 20]
ITERATIONS = 30

BENCHMARK_QUERY = "How do I troubleshoot VPN authentication after changing my password?"

RESULTS_DIR = Path("performance/results")
RESULT_FILE = RESULTS_DIR / "qdrant-benchmark.json"


# Replace these roles if your test/staging corpus
# uses different allowed_roles values.
ROLE_SCENARIOS: dict[str, list[str] | None] = {
    "no_filter": None,
    "single_role": [
        "admin",
    ],
    "multiple_roles": [
        "admin",
        "it_support",
    ],
}


def percentile(
    values: list[float],
    percentile_value: float,
) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)

    index = round((len(ordered) - 1) * percentile_value)

    return ordered[index]


def benchmark_without_auth_filter(
    *,
    top_k: int,
) -> list[float]:
    settings = get_settings()

    query_vector = embed_query(
        query=BENCHMARK_QUERY,
        model_name=settings.embedding_model_name,
    )

    client = get_qdrant_client(
        settings.qdrant_url,
        settings.qdrant_timeout_seconds,
    )

    timings_ms: list[float] = []

    for _ in range(ITERATIONS):
        started = perf_counter()

        client.query_points(
            collection_name=(settings.qdrant_collection_name),
            query=query_vector,
            limit=top_k,
            with_payload=True,
        )

        elapsed_ms = (perf_counter() - started) * 1000

        timings_ms.append(elapsed_ms)

    return timings_ms


def benchmark_qdrant(
    *,
    client: Any,
    collection_name: str,
    query_vector: list[float],
    top_k: int,
    user_roles: list[str] | None,
) -> dict[str, float | int]:
    timings_ms: list[float] = []

    authorization_filter = None

    if user_roles is not None:
        authorization_filter = build_authorization_filter(user_roles)

    #
    # Warm-up query.
    #
    # We do not include this timing because the first
    # request may include connection setup or other
    # one-time overhead.
    #
    warmup_response = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        query_filter=authorization_filter,
        limit=top_k,
        with_payload=True,
    )

    result_count = len(warmup_response.points)

    for _ in range(ITERATIONS):
        started = perf_counter()

        response = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            query_filter=authorization_filter,
            limit=top_k,
            with_payload=True,
        )

        elapsed_ms = (perf_counter() - started) * 1000

        timings_ms.append(elapsed_ms)

        result_count = len(response.points)

    return {
        "top_k": top_k,
        "iterations": ITERATIONS,
        "result_count": result_count,
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
    }


def main() -> None:
    settings = get_settings()

    print("Generating benchmark query embedding...")

    #
    # Important:
    # Disable the embedding cache if your embed_query()
    # supports this argument.
    #
    # This benchmark is intended to measure Qdrant,
    # not embedding-cache speed.
    #
    query_vector = embed_query(
        query=BENCHMARK_QUERY,
        model_name=(settings.embedding_model_name),
        cache_enabled=False,
    )

    client = get_qdrant_client(
        settings.qdrant_url,
        settings.qdrant_timeout_seconds,
    )

    all_results: list[dict[str, object]] = []

    print()
    print("Qdrant Benchmark")
    print("----------------")
    print(f"Collection: {settings.qdrant_collection_name}")
    print(f"Embedding model: {settings.embedding_model_name}")
    print(f"Iterations/test: {ITERATIONS}")

    for (
        scenario_name,
        roles,
    ) in ROLE_SCENARIOS.items():
        print()
        print(f"Scenario: {scenario_name}")

        if roles is None:
            print("Authorization filter: OFF (benchmark only)")
        else:
            print(f"Roles: {roles}")

        for top_k in TOP_K_VALUES:
            result = benchmark_qdrant(
                client=client,
                collection_name=(settings.qdrant_collection_name),
                query_vector=query_vector,
                top_k=top_k,
                user_roles=roles,
            )

            benchmark_result = {
                "scenario": scenario_name,
                "roles": roles,
                **result,
            }

            all_results.append(benchmark_result)

            print(
                f"top_k={top_k:>2} | "
                f"results="
                f"{result['result_count']:>2} | "
                f"p50="
                f"{result['p50_ms']:>8.2f}ms | "
                f"p95="
                f"{result['p95_ms']:>8.2f}ms | "
                f"p99="
                f"{result['p99_ms']:>8.2f}ms | "
                f"avg="
                f"{result['average_ms']:>8.2f}ms"
            )

    output = {
        "collection": (settings.qdrant_collection_name),
        "embedding_model": (settings.embedding_model_name),
        "query": BENCHMARK_QUERY,
        "iterations_per_test": (ITERATIONS),
        "top_k_values": (TOP_K_VALUES),
        "results": all_results,
    }

    RESULTS_DIR.mkdir(
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
    print(f"Saved benchmark: {RESULT_FILE}")


if __name__ == "__main__":
    main()
