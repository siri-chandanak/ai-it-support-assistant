import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from ai_it_support_assistant.models.performance_models import (
    PerformanceConfiguration,
    PerformanceReport,
    ScenarioPerformanceBaseline,
)

RESULTS_DIR = Path("performance/results")

LOCUST_STATS_FILE = RESULTS_DIR / "baseline_stats.csv"

ENVIRONMENT_FILE = RESULTS_DIR / "performance-environment.json"

EMBEDDING_FILE = RESULTS_DIR / "embedding-benchmark.json"

QDRANT_FILE = RESULTS_DIR / "qdrant-benchmark.json"

OUTPUT_FILE = RESULTS_DIR / "performance-baseline.json"

OPA_FILE = RESULTS_DIR / "opa-benchmark.json"

FULL_RAG_FILE = RESULTS_DIR / "full-rag-benchmark.json"

RAG_COST_FILE = RESULTS_DIR / "rag-cost-benchmark.json"

CACHE_FILE = RESULTS_DIR / "cache-benchmark.json"

WORKER_QUEUE_FILE = RESULTS_DIR / "worker-queue-benchmark.json"


def read_json(
    path: Path,
) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def read_json_optional(
    path: Path,
) -> dict | None:
    if not path.exists():
        return None

    return json.loads(path.read_text(encoding="utf-8"))


def find_full_rag_p95(
    benchmark: dict | None,
) -> float | None:
    if not benchmark:
        return None

    value = benchmark.get("p95_ms")

    if value is None:
        return None

    return float(value)


def parse_float(
    value: str | None,
) -> float:
    if value in (
        None,
        "",
        "N/A",
    ):
        return 0.0

    return float(value)


def parse_int(
    value: str | None,
) -> int:
    if value in (
        None,
        "",
        "N/A",
    ):
        return 0

    return int(float(value))


def find_pdp_p95(
    benchmark: dict | None,
) -> float | None:
    if not benchmark:
        return None

    results = benchmark.get(
        "results",
        [],
    )

    if not results:
        return None

    return max(
        float(
            item.get(
                "p95_ms",
                0,
            )
        )
        for item in results
    )


def load_locust_rows() -> list[dict[str, str]]:
    if not LOCUST_STATS_FILE.exists():
        raise FileNotFoundError(
            "Locust stats file not found: "
            f"{LOCUST_STATS_FILE}\n\n"
            "Run Locust first with:\n"
            "--csv "
            "performance/results/baseline"
        )

    with LOCUST_STATS_FILE.open(
        newline="",
        encoding="utf-8",
    ) as file:
        return list(csv.DictReader(file))


def find_aggregated_row(
    rows: list[dict[str, str]],
) -> dict[str, str]:
    for row in rows:
        if row.get("Name") == "Aggregated":
            return row

    raise RuntimeError("Locust CSV does not contain an Aggregated row.")


def build_scenario(
    *,
    row: dict[str, str],
    git_sha: str,
    environment: str,
    concurrency: int,
) -> ScenarioPerformanceBaseline:
    request_count = parse_int(row.get("Request Count"))

    failure_count = parse_int(row.get("Failure Count"))

    _total = request_count + failure_count

    error_rate = failure_count / request_count if request_count > 0 else 0.0

    return ScenarioPerformanceBaseline(
        scenario="mixed_baseline",
        git_sha=git_sha,
        environment=environment,
        concurrency=concurrency,
        request_count=request_count,
        error_rate=error_rate,
        p50_ms=parse_float(row.get("50%")),
        p95_ms=parse_float(row.get("95%")),
        p99_ms=parse_float(row.get("99%")),
        throughput_per_second=(parse_float(row.get("Requests/s"))),
    )


def find_average_input_tokens(
    benchmark: dict | None,
) -> float | None:
    if not benchmark:
        return None

    value = benchmark.get("average_input_tokens")

    if value is None:
        return None

    return float(value)


def find_average_output_tokens(
    benchmark: dict | None,
) -> float | None:
    if not benchmark:
        return None

    value = benchmark.get("average_output_tokens")

    if value is None:
        return None

    return float(value)


def find_cache_hit_ratio(
    benchmark: dict | None,
) -> float | None:
    if not benchmark:
        return None

    value = benchmark.get("cache_hit_ratio")

    if value is None:
        return None

    return float(value)


def find_worker_queue_p95(
    benchmark: dict | None,
) -> float | None:
    if not benchmark:
        return None

    value = benchmark.get("p95_ms")

    if value is None:
        return None

    return float(value)


def find_cost_per_rag_answer(
    benchmark: dict | None,
) -> float | None:
    if not benchmark:
        return None

    value = benchmark.get("estimated_cost_per_rag_answer")

    if value is None:
        return None

    return float(value)


def find_best_embedding_throughput(
    benchmark: dict | None,
) -> float | None:
    if not benchmark:
        return None

    results = benchmark.get(
        "results",
        [],
    )

    if not results:
        return None

    return max(
        float(
            item.get(
                "queries_per_second",
                0,
            )
        )
        for item in results
    )


def find_qdrant_p95(
    benchmark: dict | None,
) -> float | None:
    if not benchmark:
        return None

    results = benchmark.get(
        "results",
        [],
    )

    if not results:
        return None

    production_scenarios = {
        "single_role",
        "multiple_roles",
    }

    secured_results = [item for item in results if item.get("scenario") in production_scenarios]

    if not secured_results:
        return None

    return max(
        float(
            item.get(
                "p95_ms",
                0,
            )
        )
        for item in secured_results
    )


def main() -> None:
    environment_data = read_json(ENVIRONMENT_FILE)

    embedding_data = read_json_optional(EMBEDDING_FILE)

    qdrant_data = read_json_optional(QDRANT_FILE)

    rows = load_locust_rows()

    aggregated = find_aggregated_row(rows)

    opa_data = read_json_optional(OPA_FILE)

    full_rag_data = read_json_optional(FULL_RAG_FILE)

    rag_cost_data = read_json_optional(RAG_COST_FILE)

    cache_data = read_json_optional(CACHE_FILE)

    worker_queue_data = read_json_optional(WORKER_QUEUE_FILE)

    git_sha = environment_data.get(
        "git_sha",
        "unknown",
    )

    environment = environment_data.get(
        "environment",
        "unknown",
    )

    application = environment_data.get(
        "application",
        {},
    )

    models = environment_data.get(
        "models",
        {},
    )

    rag = environment_data.get(
        "rag",
        {},
    )

    qdrant = environment_data.get(
        "qdrant",
        {},
    )

    authorization = environment_data.get(
        "authorization",
        {},
    )

    concurrency = application.get("api_replicas") or 0

    # PERF_TEST_CONCURRENCY is better than using
    # replica count if you add it later.
    import os

    concurrency_env = os.getenv("PERF_TEST_CONCURRENCY")

    if concurrency_env:
        concurrency = int(concurrency_env)

    scenario = build_scenario(
        row=aggregated,
        git_sha=git_sha,
        environment=environment,
        concurrency=concurrency,
    )

    cache_enabled = None

    embedding_cache = rag.get("embedding_cache_enabled")

    retrieval_cache = rag.get("retrieval_cache_enabled")

    if embedding_cache is not None or retrieval_cache is not None:
        cache_enabled = bool(embedding_cache or retrieval_cache)

    configuration = PerformanceConfiguration(
        git_sha=git_sha,
        environment=environment,
        embedding_model_name=(
            models.get(
                "embedding_model",
                "unknown",
            )
        ),
        llm_model=(
            models.get(
                "llm_model",
                "unknown",
            )
        ),
        rag_top_k=int(
            rag.get(
                "top_k",
                0,
            )
        ),
        rag_score_threshold=float(
            rag.get(
                "score_threshold",
                0.0,
            )
        ),
        qdrant_collection_name=(
            qdrant.get(
                "collection",
                "unknown",
            )
        ),
        cache_enabled=cache_enabled,
        api_replicas=(application.get("api_replicas")),
        worker_replicas=(application.get("worker_replicas")),
        pdp_mode=(authorization.get("pdp_mode")),
    )

    report = PerformanceReport(
        configuration=configuration,
        scenarios=[
            scenario,
        ],
        qdrant_p95_ms=(find_qdrant_p95(qdrant_data)),
        embedding_queries_per_second=(find_best_embedding_throughput(embedding_data)),
        http_error_rate=scenario.error_rate,
        opa_p95_ms=(find_pdp_p95(opa_data)),
        rag_p95_ms=(find_full_rag_p95(full_rag_data)),
        average_input_tokens=(find_average_input_tokens(rag_cost_data)),
        average_output_tokens=(find_average_output_tokens(rag_cost_data)),
        estimated_cost_per_rag_answer=(find_cost_per_rag_answer(rag_cost_data)),
        cache_hit_ratio=(find_cache_hit_ratio(cache_data)),
        worker_queue_p95_ms=(find_worker_queue_p95(worker_queue_data)),
        generated_at_utc=(datetime.now(UTC).isoformat()),
    )

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_FILE.write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )

    print()
    print("Performance Baseline")
    print("--------------------")
    print(f"Git SHA............{git_sha[:12]}")
    print(f"Environment........{environment}")
    print(f"Requests...........{scenario.request_count}")
    print(f"Error rate.........{scenario.error_rate * 100:.2f}%")
    print(f"p50................{scenario.p50_ms:.2f} ms")
    print(f"p95................{scenario.p95_ms:.2f} ms")
    print(f"p99................{scenario.p99_ms:.2f} ms")
    print(f"Throughput.........{scenario.throughput_per_second:.2f} req/s")

    if report.qdrant_p95_ms is not None:
        print(f"Qdrant secured p95................{report.qdrant_p95_ms:.2f} ms")

    if report.embedding_queries_per_second is not None:
        print(f"Embedding max QPS..{report.embedding_queries_per_second:.2f}")

    if report.opa_p95_ms is not None:
        print(f"PDP worst p95......{report.opa_p95_ms:.2f} ms")

    print()
    print(f"Saved baseline: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
