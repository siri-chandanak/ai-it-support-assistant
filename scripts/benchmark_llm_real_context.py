from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, median
from time import perf_counter

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.services.llm_service import (
    generate_grounded_answer,
)
from ai_it_support_assistant.services.rag_service import (
    build_context,
)
from ai_it_support_assistant.services.retrieval_service import (
    retrieve_chunks,
)

ITERATIONS = 10

QUESTION = "What should a user do when VPN login fails?"

RESULT_FILE = Path("performance/results/llm-real-context-benchmark.json")


def percentile(
    values: list[float],
    percentile_value: float,
) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)

    index = round((len(ordered) - 1) * percentile_value)

    return ordered[index]


def main() -> None:
    settings = get_settings()

    print()
    print("LLM Real-Context Benchmark")
    print("--------------------------")

    #
    # Retrieve the same kind of evidence
    # used by the real RAG path.
    #
    retrieved_chunks = retrieve_chunks(
        query=QUESTION,
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

    relevant_chunks = [
        chunk for chunk in retrieved_chunks if chunk.score >= settings.rag_score_threshold
    ]

    if not relevant_chunks:
        raise RuntimeError("No chunks passed the RAG score threshold.")

    context = build_context(relevant_chunks)

    print(f"Retrieved chunks: {len(retrieved_chunks)}")
    print(f"Relevant chunks: {len(relevant_chunks)}")
    print(f"Context characters: {len(context)}")
    print(f"Model: {settings.llm_model}")
    print(f"Iterations: {ITERATIONS}")

    timings_ms: list[float] = []
    errors: list[str] = []

    #
    # Warm-up.
    #
    print()
    print("Warm-up LLM request...")

    started = perf_counter()

    try:
        generate_grounded_answer(
            question=QUESTION,
            context=context,
            api_key=(settings.openai_api_key),
            model_name=(settings.llm_model),
            timeout_seconds=(settings.openai_timeout_seconds),
            max_retries=(settings.openai_max_retries),
        )

        warmup_ms = (perf_counter() - started) * 1000

        print(f"Warm-up latency: {warmup_ms:.2f} ms")

    except Exception as exc:
        warmup_ms = (perf_counter() - started) * 1000

        print(f"Warm-up failed after {warmup_ms:.2f} ms: {type(exc).__name__}: {exc}")

    print()
    print("Measured requests:")

    for iteration in range(
        1,
        ITERATIONS + 1,
    ):
        started = perf_counter()

        try:
            output = generate_grounded_answer(
                question=QUESTION,
                context=context,
                api_key=(settings.openai_api_key),
                model_name=(settings.llm_model),
                timeout_seconds=(settings.openai_timeout_seconds),
                max_retries=(settings.openai_max_retries),
            )

            elapsed_ms = (perf_counter() - started) * 1000

            timings_ms.append(elapsed_ms)

            print(
                f"{iteration:02d}: "
                f"{elapsed_ms:.2f} ms "
                f"OK "
                f"insufficient_context="
                f"{output.insufficient_context}"
            )

        except Exception as exc:
            elapsed_ms = (perf_counter() - started) * 1000

            timings_ms.append(elapsed_ms)

            error_message = f"{type(exc).__name__}: {exc}"

            errors.append(error_message)

            print(f"{iteration:02d}: {elapsed_ms:.2f} ms ERROR {error_message}")

    result = {
        "model": settings.llm_model,
        "context_characters": len(context),
        "retrieved_chunks": (len(retrieved_chunks)),
        "relevant_chunks": (len(relevant_chunks)),
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
        "error_count": len(errors),
        "errors": errors,
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
    print("Benchmark Summary")
    print("-----------------")
    print(f"context={result['context_characters']} chars")
    print(f"p50={result['p50_ms']:.2f} ms")
    print(f"p95={result['p95_ms']:.2f} ms")
    print(f"p99={result['p99_ms']:.2f} ms")
    print(f"errors={result['error_count']}")

    print()
    print(f"Saved benchmark: {RESULT_FILE}")


if __name__ == "__main__":
    main()
