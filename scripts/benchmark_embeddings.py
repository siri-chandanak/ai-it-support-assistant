import json
from pathlib import Path
from time import perf_counter

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.services.embedding_service import (
    get_embedding_model,
)

BATCH_SIZES = [1, 10, 100]

RESULTS_DIR = Path("performance/results")
RESULT_FILE = RESULTS_DIR / "embedding-benchmark.json"


def benchmark_batch(
    *,
    model,
    batch_size: int,
) -> dict[str, float | int]:
    texts = [
        (f"Performance benchmark query {index}: How do I troubleshoot VPN authentication?")
        for index in range(batch_size)
    ]

    started = perf_counter()

    model.encode(
        texts,
        normalize_embeddings=True,
    )

    duration_seconds = perf_counter() - started

    queries_per_second = batch_size / duration_seconds if duration_seconds > 0 else 0.0

    average_ms_per_query = (duration_seconds / batch_size) * 1000

    return {
        "batch_size": batch_size,
        "total_seconds": round(
            duration_seconds,
            4,
        ),
        "queries_per_second": round(
            queries_per_second,
            2,
        ),
        "average_ms_per_query": round(
            average_ms_per_query,
            2,
        ),
    }


def main() -> None:
    settings = get_settings()

    print("Loading embedding model...")
    print(f"Model: {settings.embedding_model_name}")

    model = get_embedding_model(settings.embedding_model_name)

    # Warm up the model before timing.
    # Otherwise the first benchmark would include model
    # initialization/runtime warm-up overhead.
    model.encode(
        ["embedding benchmark warmup"],
        normalize_embeddings=True,
    )

    results: list[dict[str, float | int]] = []

    print()
    print("Embedding Benchmark")
    print("-------------------")

    for batch_size in BATCH_SIZES:
        result = benchmark_batch(
            model=model,
            batch_size=batch_size,
        )

        results.append(result)

        print(
            f"batch={result['batch_size']:>3} | "
            f"total={result['total_seconds']:.4f}s | "
            f"qps={result['queries_per_second']:.2f} | "
            f"avg={result['average_ms_per_query']:.2f}ms/query"
        )

    output = {
        "model": settings.embedding_model_name,
        "results": results,
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
