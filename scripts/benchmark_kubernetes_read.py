from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, median
from time import perf_counter

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.services.kubernetes_state_service import (
    get_kubernetes_resource_state,
)

ITERATIONS = 10

RESOURCE_TYPE = "deployment"
RESOURCE_NAME = "ai-support-mcp"
NAMESPACE = "ai-support"

RESULT_FILE = Path("performance/results/kubernetes-read-benchmark.json")


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

    timings_ms: list[float] = []
    errors: list[str] = []

    print()
    print("Kubernetes Read Benchmark")
    print("-------------------------")
    print(f"Config mode: {settings.kubernetes_config_mode}")
    print(f"Context: {settings.kubernetes_context}")
    print(f"Resource: {NAMESPACE}/{RESOURCE_NAME}")
    print(f"Iterations: {ITERATIONS}")

    #
    # Warm-up / cold-start measurement.
    #
    print()
    print("Warm-up Kubernetes request...")

    warmup_started = perf_counter()

    warmup_error: str | None = None

    try:
        get_kubernetes_resource_state(
            resource_type=RESOURCE_TYPE,
            name=RESOURCE_NAME,
            namespace=NAMESPACE,
            config_mode=(settings.kubernetes_config_mode),
            context=(settings.kubernetes_context),
        )

        cold_start_ms = (perf_counter() - warmup_started) * 1000

        print(f"Cold-start latency: {cold_start_ms:.2f} ms")

    except Exception as exc:
        cold_start_ms = (perf_counter() - warmup_started) * 1000

        warmup_error = f"{type(exc).__name__}: {exc}"

        print(f"Warm-up failed after {cold_start_ms:.2f} ms ERROR {warmup_error}")

    #
    # Steady-state measured requests.
    #
    print()
    print("Measured warm requests:")

    for iteration in range(
        1,
        ITERATIONS + 1,
    ):
        started = perf_counter()

        try:
            get_kubernetes_resource_state(
                resource_type=RESOURCE_TYPE,
                name=RESOURCE_NAME,
                namespace=NAMESPACE,
                config_mode=(settings.kubernetes_config_mode),
                context=(settings.kubernetes_context),
            )

            elapsed_ms = (perf_counter() - started) * 1000

            timings_ms.append(elapsed_ms)

            print(f"{iteration:02d}: {elapsed_ms:.2f} ms OK")

        except Exception as exc:
            elapsed_ms = (perf_counter() - started) * 1000

            timings_ms.append(elapsed_ms)

            error_message = f"{type(exc).__name__}: {exc}"

            errors.append(error_message)

            print(f"{iteration:02d}: {elapsed_ms:.2f} ms ERROR {error_message}")

    output = {
        "resource_type": RESOURCE_TYPE,
        "resource_name": RESOURCE_NAME,
        "namespace": NAMESPACE,
        "config_mode": (settings.kubernetes_config_mode),
        "context": (settings.kubernetes_context),
        "cold_start_ms": round(
            cold_start_ms,
            2,
        ),
        "warmup_error": warmup_error,
        "iterations": ITERATIONS,
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
    print("Benchmark Summary")
    print("-----------------")
    print(f"cold_start={output['cold_start_ms']:.2f} ms")
    print(f"p50={output['p50_ms']:.2f} ms")
    print(f"p95={output['p95_ms']:.2f} ms")
    print(f"p99={output['p99_ms']:.2f} ms")
    print(f"errors={output['error_count']}")

    print()
    print(f"Saved benchmark: {RESULT_FILE}")


if __name__ == "__main__":
    main()
