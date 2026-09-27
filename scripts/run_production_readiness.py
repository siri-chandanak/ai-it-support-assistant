import json
from pathlib import Path
from typing import Any

PERFORMANCE_BASELINE_PATH = Path("performance/results/performance-baseline.json")


def read_performance_baseline_status() -> tuple[
    str,
    dict[str, Any] | None,
]:
    if not PERFORMANCE_BASELINE_PATH.exists():
        return "PARTIAL", None

    try:
        with PERFORMANCE_BASELINE_PATH.open(
            "r",
            encoding="utf-8",
        ) as file:
            baseline = json.load(file)
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return "PARTIAL", None

    rag_p95_ms = baseline.get("rag_p95_ms")
    qdrant_p95_ms = baseline.get("qdrant_p95_ms")
    opa_p95_ms = baseline.get("opa_p95_ms")
    error_rate = baseline.get("http_error_rate")
    false_allows = baseline.get(
        "false_allows",
        0,
    )

    required_values = [
        rag_p95_ms,
        qdrant_p95_ms,
        opa_p95_ms,
        error_rate,
    ]

    if any(value is None for value in required_values):
        return "PARTIAL", baseline

    passed = (
        float(rag_p95_ms) <= 3_000
        and float(qdrant_p95_ms) <= 200
        and float(opa_p95_ms) <= 100
        and float(error_rate) < 0.01
        and int(false_allows) == 0
    )

    return (
        "PASS" if passed else "FAIL",
        baseline,
    )
