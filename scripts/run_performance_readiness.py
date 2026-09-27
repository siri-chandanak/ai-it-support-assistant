from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

BASELINE_PATH = Path("performance/results/performance-baseline.json")


# Engineering benchmark budgets.
#
# These are NOT production SLOs.
RAG_P95_BUDGET_MS = 6000.0

RAG_P95_OPTIMIZATION_TARGET_MS = 3000.0
QDRANT_P95_BUDGET_MS = 200.0
OPA_P95_BUDGET_MS = 100.0
WORKER_QUEUE_P95_BUDGET_MS = 10_000.0
HTTP_ERROR_RATE_BUDGET = 0.01

# Security is never relaxed for performance.
MAX_FALSE_ALLOWS = 0


def load_baseline() -> dict[str, Any]:
    if not BASELINE_PATH.exists():
        raise FileNotFoundError(
            "Performance baseline not found at "
            f"{BASELINE_PATH}. "
            "Run scripts/run_performance_baseline.py first."
        )

    with BASELINE_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError("Performance baseline must contain a JSON object.")

    return data


def get_float(
    data: dict[str, Any],
    key: str,
    *,
    default: float | None = None,
) -> float | None:
    value = data.get(key)

    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_int(
    data: dict[str, Any],
    key: str,
    *,
    default: int | None = None,
) -> int | None:
    value = data.get(key)

    if value is None:
        return default

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def pass_fail(
    value: float | int | None,
    *,
    maximum: float | int,
) -> str:
    if value is None:
        return "PARTIAL"

    if value <= maximum:
        return "PASS"

    return "FAIL"


def format_ms(
    value: float | None,
) -> str:
    if value is None:
        return "N/A"

    if value >= 1_000:
        return f"{value / 1000:.2f}s"

    return f"{value:.0f}ms"


def format_percent(
    value: float | None,
) -> str:
    if value is None:
        return "N/A"

    return f"{value * 100:.2f}%"


def format_cost(
    value: float | None,
) -> str:
    if value is None:
        return "N/A"

    return f"${value:.6f}"


def print_result(
    label: str,
    value: str,
    status: str | None = None,
) -> None:
    dots = "." * max(
        1,
        28 - len(label),
    )

    if status:
        print(f"{label}{dots}{value} {status}")
    else:
        print(f"{label}{dots}{value}")


def main() -> int:
    try:
        baseline = load_baseline()
    except (
        FileNotFoundError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(
            f"Performance readiness unavailable: {exc}",
            file=sys.stderr,
        )
        return 2

    rag_p95_ms = get_float(
        baseline,
        "rag_p95_ms",
    )

    qdrant_p95_ms = get_float(
        baseline,
        "qdrant_p95_ms",
    )

    opa_p95_ms = get_float(
        baseline,
        "opa_p95_ms",
    )

    http_error_rate = get_float(
        baseline,
        "http_error_rate",
    )

    worker_queue_p95_ms = get_float(
        baseline,
        "worker_queue_p95_ms",
    )

    cache_hit_ratio = get_float(
        baseline,
        "cache_hit_ratio",
    )

    avg_input_tokens = get_float(
        baseline,
        "average_input_tokens",
        default=0.0,
    )

    avg_output_tokens = get_float(
        baseline,
        "average_output_tokens",
        default=0.0,
    )

    cost_per_rag_answer = get_float(
        baseline,
        "estimated_cost_per_rag_answer",
    )

    false_allows = get_int(
        baseline,
        "false_allows",
        default=0,
    )

    rag_status = pass_fail(
        rag_p95_ms,
        maximum=RAG_P95_BUDGET_MS,
    )

    qdrant_status = pass_fail(
        qdrant_p95_ms,
        maximum=QDRANT_P95_BUDGET_MS,
    )

    opa_status = pass_fail(
        opa_p95_ms,
        maximum=OPA_P95_BUDGET_MS,
    )

    error_status = pass_fail(
        http_error_rate,
        maximum=HTTP_ERROR_RATE_BUDGET,
    )

    worker_status = pass_fail(
        worker_queue_p95_ms,
        maximum=WORKER_QUEUE_P95_BUDGET_MS,
    )

    security_status = pass_fail(
        false_allows,
        maximum=MAX_FALSE_ALLOWS,
    )

    statuses = [
        rag_status,
        qdrant_status,
        opa_status,
        error_status,
        worker_status,
        security_status,
    ]

    if "FAIL" in statuses:
        overall = "FAIL"
    elif "PARTIAL" in statuses:
        overall = "PARTIAL"
    else:
        overall = "PASS"

    avg_total_tokens = (avg_input_tokens or 0.0) + (avg_output_tokens or 0.0)

    print()
    print("Performance Readiness")
    print("---------------------")
    print()

    print_result(
        "RAG p95",
        format_ms(rag_p95_ms),
        rag_status,
    )

    print_result(
        "Qdrant p95",
        format_ms(qdrant_p95_ms),
        qdrant_status,
    )

    print_result(
        "OPA p95",
        format_ms(opa_p95_ms),
        opa_status,
    )

    print_result(
        "HTTP error rate",
        format_percent(http_error_rate),
        error_status,
    )

    print_result(
        "Worker queue p95",
        format_ms(worker_queue_p95_ms),
        worker_status,
    )

    print_result(
        "False allows",
        str(false_allows),
        security_status,
    )

    print_result(
        "Cache hit ratio",
        format_percent(cache_hit_ratio),
    )

    print_result(
        "Avg LLM tokens",
        f"{avg_total_tokens:,.0f}",
    )

    print_result(
        "Cost / RAG answer",
        format_cost(cost_per_rag_answer),
    )

    print()
    print_result(
        "RESULT",
        overall,
    )
    print()

    if overall == "FAIL":
        return 1

    if overall == "PARTIAL":
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
