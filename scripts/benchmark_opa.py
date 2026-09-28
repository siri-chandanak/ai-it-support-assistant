from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, median
from time import perf_counter

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.db.session import get_session_factory
from ai_it_support_assistant.schemas.policy import (
    PolicyContext,
    PolicyRequest,
    PolicyResource,
    PolicySubject,
)
from ai_it_support_assistant.services.pdp.factory import (
    get_policy_decision_point,
)
from ai_it_support_assistant.services.policy_decision_service import (
    decide_policy,
)

ITERATIONS = 30

RESULTS_DIR = Path("performance/results")
RESULT_FILE = RESULTS_DIR / "opa-benchmark.json"


def percentile(
    values: list[float],
    percentile_value: float,
) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)

    index = round((len(ordered) - 1) * percentile_value)

    return ordered[index]


def build_requests() -> dict[str, PolicyRequest]:
    return {
        "service_status_allowed": PolicyRequest(
            subject=PolicySubject(
                subject_id="performance-admin",
                username="performance-admin",
                roles=["admin"],
            ),
            action="service_status.read",
            resource=PolicyResource(
                resource_type="service",
                resource_id="vpn-gateway",
            ),
            context=PolicyContext(),
        ),
        "kubernetes_denied": PolicyRequest(
            subject=PolicySubject(
                subject_id="performance-admin",
                username="performance-admin",
                roles=["admin"],
            ),
            action="kubernetes.read",
            resource=PolicyResource(
                resource_type="kubernetes",
                resource_id="ai-support-api",
                attributes={
                    "namespace": "dev",
                    "resource_type": "deployment",
                },
            ),
            context=PolicyContext(),
        ),
    }


def benchmark_scenario(
    *,
    name: str,
    request: PolicyRequest,
    pdp,
    session,
) -> dict:
    timings_ms: list[float] = []

    allowed_count = 0
    denied_count = 0
    error_count = 0

    #
    # Warm-up.
    #
    try:
        decide_policy(
            pdp=pdp,
            request=request,
            session=session,
        )
    except Exception:
        pass

    for _ in range(ITERATIONS):
        started = perf_counter()

        try:
            decision = decide_policy(
                pdp=pdp,
                request=request,
                session=session,
            )

            elapsed_ms = (perf_counter() - started) * 1000

            timings_ms.append(elapsed_ms)

            if decision.allowed:
                allowed_count += 1
            else:
                denied_count += 1

        except Exception:
            elapsed_ms = (perf_counter() - started) * 1000

            timings_ms.append(elapsed_ms)

            error_count += 1

    return {
        "scenario": name,
        "iterations": ITERATIONS,
        "allowed_count": allowed_count,
        "denied_count": denied_count,
        "error_count": error_count,
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

    pdp = get_policy_decision_point(
        mode=settings.policy_pdp_mode,
        opa_url=settings.opa_url,
        opa_policy_path=settings.opa_policy_path,
        opa_timeout_seconds=(settings.opa_timeout_seconds),
        opa_max_attempts=(settings.opa_max_attempts),
    )

    session_factory = get_session_factory(settings.database_url)

    requests = build_requests()

    all_results: list[dict] = []

    print()
    print("OPA / PDP Benchmark")
    print("-------------------")
    print(f"PDP mode: {settings.policy_pdp_mode}")
    print(f"Iterations/test: {ITERATIONS}")

    with session_factory() as session:
        for (
            scenario_name,
            request,
        ) in requests.items():
            result = benchmark_scenario(
                name=scenario_name,
                request=request,
                pdp=pdp,
                session=session,
            )

            all_results.append(result)

            print()
            print(f"{scenario_name}")
            print(
                f"p50="
                f"{result['p50_ms']:.2f}ms | "
                f"p95="
                f"{result['p95_ms']:.2f}ms | "
                f"p99="
                f"{result['p99_ms']:.2f}ms | "
                f"errors="
                f"{result['error_count']}"
            )

    output = {
        "pdp_mode": (settings.policy_pdp_mode),
        "iterations_per_test": (ITERATIONS),
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
