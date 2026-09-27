from ai_it_support_assistant.evaluation.models import (
    AutoscalingRecommendation,
)


def recommend(
    *,
    cpu_percent: float,
    rag_p95_ms: float,
    queue_depth: int,
    queue_delay_p95_ms: float,
) -> AutoscalingRecommendation:
    notes: list[str] = []

    if cpu_percent >= 70 and rag_p95_ms >= 2500:
        api_signal = "cpu"

        notes.append(
            "API latency increases with CPU "
            "pressure; CPU-based HPA may be "
            "a reasonable initial signal."
        )
    else:
        api_signal = "rag_inflight_requests"

        notes.append(
            "CPU does not clearly explain "
            "RAG latency; request concurrency "
            "is likely a better scaling signal."
        )

    worker_signal = "queue_depth"

    if queue_delay_p95_ms > 10_000:
        notes.append(
            "Worker queue delay exceeds 10 seconds; queue-based scaling should be evaluated."
        )

    if queue_depth == 0:
        notes.append(
            "No worker backlog was observed; "
            "do not increase worker replicas "
            "without additional evidence."
        )

    return AutoscalingRecommendation(
        api_scaling_signal=api_signal,
        worker_scaling_signal=(worker_signal),
        observed_api_cpu_percent=(cpu_percent),
        observed_rag_p95_ms=(rag_p95_ms),
        queue_depth=queue_depth,
        queue_delay_p95_ms=(queue_delay_p95_ms),
        recommendation_notes=notes,
    )


def main() -> None:
    # Replace these with values read from
    # your baseline artifact later.
    result = recommend(
        cpu_percent=55,
        rag_p95_ms=2800,
        queue_depth=12,
        queue_delay_p95_ms=8500,
    )

    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
