from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, median
from time import perf_counter

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.services.llm_service import (
    generate_grounded_answer,
)

ITERATIONS = 10

QUESTION = "What should a user do when VPN login fails?"

CONTEXT = """
[Source 1]
If VPN authentication fails after a password change,
the user should update any stored VPN credentials,
disconnect the existing VPN session, and reconnect
using the new password.

[Source 2]
If authentication continues to fail, verify that the
account is not locked and contact the IT support team
for further assistance.
""".strip()

RESULT_FILE = Path("performance/results/llm-benchmark.json")


def percentile(
    values: list[float],
    percentile_value: float,
) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)

    index = round((len(ordered) - 1) * percentile_value)

    return ordered[index]


def run_llm(
    *,
    settings,
):
    return generate_grounded_answer(
        question=QUESTION,
        context=CONTEXT,
        api_key=settings.openai_api_key,
        model_name=settings.llm_model,
        timeout_seconds=(settings.openai_timeout_seconds),
        max_retries=(settings.openai_max_retries),
    )


def main() -> None:
    settings = get_settings()

    timings_ms: list[float] = []
    errors: list[str] = []

    print()
    print("LLM Benchmark")
    print("-------------")
    print(f"Model: {settings.llm_model}")
    print(f"Iterations: {ITERATIONS}")
    print(f"Context characters: {len(CONTEXT)}")

    #
    # Warm-up request.
    #
    print()
    print("Warm-up LLM request...")

    warmup_started = perf_counter()

    try:
        output = run_llm(
            settings=settings,
        )

        warmup_ms = (perf_counter() - warmup_started) * 1000

        print(f"Warm-up latency: {warmup_ms:.2f} ms")

        print(f"Warm-up insufficient_context={output.insufficient_context}")

    except Exception as exc:
        warmup_ms = (perf_counter() - warmup_started) * 1000

        print(f"Warm-up failed after {warmup_ms:.2f} ms: {type(exc).__name__}: {exc}")

    #
    # Measured requests.
    #
    print()
    print("Measured LLM requests:")

    for iteration in range(
        1,
        ITERATIONS + 1,
    ):
        started = perf_counter()

        try:
            output = run_llm(
                settings=settings,
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

    output_data = {
        "model": settings.llm_model,
        "question": QUESTION,
        "context_characters": len(CONTEXT),
        "iterations": ITERATIONS,
        "warmup_ms": round(
            warmup_ms,
            2,
        ),
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
            output_data,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("LLM Benchmark Summary")
    print("---------------------")
    print(f"warmup={output_data['warmup_ms']:.2f} ms")
    print(f"p50={output_data['p50_ms']:.2f} ms")
    print(f"p95={output_data['p95_ms']:.2f} ms")
    print(f"p99={output_data['p99_ms']:.2f} ms")
    print(f"errors={output_data['error_count']}")

    print()
    print(f"Saved benchmark: {RESULT_FILE}")


if __name__ == "__main__":
    main()
