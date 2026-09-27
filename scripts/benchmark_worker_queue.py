from __future__ import annotations

import json
import time
from pathlib import Path
from statistics import mean, median

from ai_it_support_assistant.db.session import SessionLocal
from ai_it_support_assistant.repositories.approval_repository import (
    claim_action_for_execution,
    get_pending_action,
    mark_action_failed,
)
from ai_it_support_assistant.schemas.incident import (
    IncidentCreateRequest,
)
from ai_it_support_assistant.services.approval_service import (
    approve_pending_action,
    create_pending_incident_action,
)

ITERATIONS = 10

CONTROLLED_QUEUE_DELAY_SECONDS = 0.25

BENCHMARK_USERNAME = "admin"

RESULT_FILE = Path("performance/results/worker-queue-benchmark.json")


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
    queue_delays_ms: list[float] = []
    errors: list[str] = []

    worker_id = "performance-worker"

    print()
    print("Worker Queue Benchmark")
    print("----------------------")
    print(f"Iterations: {ITERATIONS}")
    print(f"Controlled wait: {CONTROLLED_QUEUE_DELAY_SECONDS:.2f}s")
    print(f"Username: {BENCHMARK_USERNAME}")

    for iteration in range(
        1,
        ITERATIONS + 1,
    ):
        approval_id: str | None = None

        try:
            #
            # 1. Create synthetic incident proposal.
            #
            with SessionLocal() as session:
                incident = IncidentCreateRequest(
                    title=("Performance benchmark incident"),
                    description=("Synthetic worker queue performance benchmark."),
                    severity="low",
                    service_name="performance-test",
                )

                pending = create_pending_incident_action(
                    session=session,
                    requested_by=(BENCHMARK_USERNAME),
                    incident=incident,
                )

                session.commit()

                approval_id = pending.approval_id

            #
            # 2. Approve action.
            #
            with SessionLocal() as session:
                approved = approve_pending_action(
                    session=session,
                    approval_id=approval_id,
                    approved_by=(BENCHMARK_USERNAME),
                )

                session.commit()

                expected_version = approved.version

            #
            # 3. Debug committed approval state
            # using a NEW session.
            #
            with SessionLocal() as session:
                check_action = get_pending_action(
                    session=session,
                    approval_id=approval_id,
                )

                if check_action is None:
                    raise RuntimeError("Action disappeared after approval.")

                print()
                print(
                    "AFTER APPROVAL:",
                    f"state={check_action.state}",
                    f"approved_at={check_action.approved_at}",
                    f"execution_started_at={check_action.execution_started_at}",
                    f"version={check_action.version}",
                )

            #
            # 4. Intentional queue delay.
            #
            time.sleep(CONTROLLED_QUEUE_DELAY_SECONDS)

            #
            # 5. Claim action exactly like
            # worker claim path.
            #
            with SessionLocal() as session:
                claim_action_for_execution(
                    session=session,
                    approval_id=approval_id,
                    expected_version=(expected_version),
                    worker_id=worker_id,
                )

                session.commit()

            #
            # 6. Reload committed claim state
            # using a NEW session.
            #
            with SessionLocal() as session:
                claimed = get_pending_action(
                    session=session,
                    approval_id=approval_id,
                )

                if claimed is None:
                    raise RuntimeError("Claimed action disappeared.")

                print(
                    "AFTER CLAIM:",
                    f"state={claimed.state}",
                    f"approved_at={claimed.approved_at}",
                    f"execution_started_at={claimed.execution_started_at}",
                    f"version={claimed.version}",
                )

                #
                # Debug each timestamp separately.
                #
                if claimed.approved_at is None:
                    raise RuntimeError("approved_at is missing.")

                if claimed.execution_started_at is None:
                    raise RuntimeError("execution_started_at is missing.")

                queue_delay_seconds = (
                    claimed.execution_started_at - claimed.approved_at
                ).total_seconds()

                queue_delay_ms = max(
                    queue_delay_seconds * 1000,
                    0.0,
                )

                queue_delays_ms.append(queue_delay_ms)

                print(f"{iteration:02d}: {queue_delay_ms:.2f} ms OK")

                #
                # 7. Cleanup.
                #
                # We don't want the benchmark
                # to create an actual incident.
                #
                mark_action_failed(
                    session=session,
                    approval_id=approval_id,
                    expected_version=(claimed.version),
                    failure_reason=("performance_benchmark"),
                    result_json=None,
                )

                session.commit()

        except Exception as exc:
            error_message = f"{type(exc).__name__}: {exc}"

            errors.append(error_message)

            print(f"{iteration:02d}: ERROR {error_message}")

    #
    # If debug failed, stop here.
    #
    if not queue_delays_ms:
        print()
        print("No successful queue-delay measurements.")
        print("Check AFTER APPROVAL and AFTER CLAIM above.")

        return

    result = {
        "iterations": ITERATIONS,
        "controlled_wait_seconds": (CONTROLLED_QUEUE_DELAY_SECONDS),
        "successful_measurements": (len(queue_delays_ms)),
        "error_count": len(errors),
        "average_ms": round(
            mean(queue_delays_ms),
            2,
        ),
        "p50_ms": round(
            median(queue_delays_ms),
            2,
        ),
        "p95_ms": round(
            percentile(
                queue_delays_ms,
                0.95,
            ),
            2,
        ),
        "p99_ms": round(
            percentile(
                queue_delays_ms,
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
            result,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("Worker Queue Summary")
    print("--------------------")
    print(f"p50={result['p50_ms']:.2f} ms")
    print(f"p95={result['p95_ms']:.2f} ms")
    print(f"p99={result['p99_ms']:.2f} ms")
    print(f"errors={result['error_count']}")

    print()
    print(f"Saved benchmark: {RESULT_FILE}")


if __name__ == "__main__":
    main()
