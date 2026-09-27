from __future__ import annotations

import json
from pathlib import Path

from prometheus_client import Counter

from ai_it_support_assistant.cache.cache_service import (
    configure_embedding_cache,
    configure_retrieval_cache,
)
from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.observability.metrics import (
    EMBEDDING_CACHE_HITS,
    EMBEDDING_CACHE_MISSES,
    RETRIEVAL_CACHE_HITS,
    RETRIEVAL_CACHE_MISSES,
)
from ai_it_support_assistant.services.retrieval_service import (
    retrieve_chunks,
)

ITERATIONS = 20

QUERY = "What should a user do when VPN login fails?"

RESULT_FILE = Path("performance/results/cache-benchmark.json")


def counter_value(
    counter: Counter,
) -> float:
    total = 0.0

    for metric in counter.collect():
        for sample in metric.samples:
            if sample.name.endswith("_total"):
                total += float(sample.value)

    return total


def calculate_ratio(
    *,
    hits: float,
    misses: float,
) -> float | None:
    total = hits + misses

    if total == 0:
        return None

    return hits / total


def main() -> None:
    settings = get_settings()

    #
    # IMPORTANT:
    # This benchmark is its own Python process.
    # Therefore initialize the in-memory caches here.
    #
    configure_embedding_cache(
        max_size=settings.embedding_cache_max_size,
        ttl_seconds=settings.embedding_cache_ttl_seconds,
    )

    configure_retrieval_cache(
        max_size=settings.retrieval_cache_max_size,
        ttl_seconds=settings.retrieval_cache_ttl_seconds,
    )

    embedding_hits_before = counter_value(EMBEDDING_CACHE_HITS)
    embedding_misses_before = counter_value(EMBEDDING_CACHE_MISSES)

    retrieval_hits_before = counter_value(RETRIEVAL_CACHE_HITS)
    retrieval_misses_before = counter_value(RETRIEVAL_CACHE_MISSES)

    print()
    print("Cache Benchmark")
    print("---------------")
    print(f"Iterations: {ITERATIONS}")
    print(f"Query: {QUERY}")

    errors = 0

    for iteration in range(
        1,
        ITERATIONS + 1,
    ):
        try:
            chunks = retrieve_chunks(
                query=QUERY,
                top_k=settings.rag_top_k,
                embedding_model_name=(settings.embedding_model_name),
                embedding_cache_enabled=(settings.embedding_cache_enabled),
                retrieval_cache_enabled=(settings.retrieval_cache_enabled),
                qdrant_url=settings.qdrant_url,
                collection_name=(settings.qdrant_collection_name),
                qdrant_timeout_seconds=(settings.qdrant_timeout_seconds),
                qdrant_max_retries=(settings.qdrant_max_attempts),
                user_roles=["admin"],
            )

            print(f"{iteration:02d}: OK chunks={len(chunks)}")

        except Exception as exc:
            errors += 1

            print(f"{iteration:02d}: ERROR {type(exc).__name__}: {exc}")

    embedding_hits = counter_value(EMBEDDING_CACHE_HITS) - embedding_hits_before

    embedding_misses = counter_value(EMBEDDING_CACHE_MISSES) - embedding_misses_before

    retrieval_hits = counter_value(RETRIEVAL_CACHE_HITS) - retrieval_hits_before

    retrieval_misses = counter_value(RETRIEVAL_CACHE_MISSES) - retrieval_misses_before

    embedding_ratio = calculate_ratio(
        hits=embedding_hits,
        misses=embedding_misses,
    )

    retrieval_ratio = calculate_ratio(
        hits=retrieval_hits,
        misses=retrieval_misses,
    )

    #
    # For the production RAG request path, retrieval cache
    # is the outer cache. Therefore use its hit ratio as the
    # primary readiness cache_hit_ratio.
    #
    cache_hit_ratio = retrieval_ratio

    result = {
        "iterations": ITERATIONS,
        "errors": errors,
        "embedding": {
            "hits": embedding_hits,
            "misses": embedding_misses,
            "hit_ratio": embedding_ratio,
        },
        "retrieval": {
            "hits": retrieval_hits,
            "misses": retrieval_misses,
            "hit_ratio": retrieval_ratio,
        },
        "cache_hit_ratio": cache_hit_ratio,
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
    print("Cache Benchmark Summary")
    print("-----------------------")

    print(f"Embedding hits.........{embedding_hits:.0f}")
    print(f"Embedding misses.......{embedding_misses:.0f}")

    if embedding_ratio is not None:
        print(f"Embedding hit ratio....{embedding_ratio * 100:.2f}%")
    else:
        print("Embedding hit ratio....N/A")

    print(f"Retrieval hits.........{retrieval_hits:.0f}")
    print(f"Retrieval misses.......{retrieval_misses:.0f}")

    if retrieval_ratio is not None:
        print(f"Retrieval hit ratio....{retrieval_ratio * 100:.2f}%")
    else:
        print("Retrieval hit ratio....N/A")

    print(f"Errors.................{errors}")

    print()
    print(f"Saved benchmark: {RESULT_FILE}")


if __name__ == "__main__":
    main()
