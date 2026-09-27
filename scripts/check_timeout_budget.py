from ai_it_support_assistant.core.config import (
    get_settings,
)


def main() -> None:
    settings = get_settings()

    qdrant_timeout = settings.qdrant_timeout_seconds

    qdrant_attempts = settings.qdrant_max_attempts

    llm_timeout = getattr(
        settings,
        "llm_timeout_seconds",
        getattr(
            settings,
            "openai_timeout_seconds",
            0.0,
        ),
    )

    llm_retries = getattr(
        settings,
        "llm_max_retries",
        getattr(
            settings,
            "openai_max_retries",
            0,
        ),
    )

    overall_timeout = getattr(
        settings,
        "rag_request_timeout_seconds",
        0.0,
    )

    qdrant_retry_wait_budget = 0.0

    for attempt in range(
        1,
        qdrant_attempts,
    ):
        wait_seconds = min(
            2 ** (attempt - 1),
            4,
        )

        qdrant_retry_wait_budget += wait_seconds

    qdrant_worst_case = qdrant_timeout * qdrant_attempts + qdrant_retry_wait_budget

    #
    # Treat the LLM timeout as the client-level
    # timeout budget.
    #
    # We display retry configuration separately
    # because different LLM clients account for
    # retry timing differently.
    #
    estimated_sequential_budget = qdrant_worst_case + llm_timeout

    print("Timeout Budget")
    print("--------------")

    print(f"Qdrant timeout/attempt: {qdrant_timeout:.1f}s")

    print(f"Qdrant max attempts:    {qdrant_attempts}")

    print(f"Qdrant retry waits:     {qdrant_retry_wait_budget:.1f}s")

    print(f"Qdrant worst case:      {qdrant_worst_case:.1f}s")

    print(f"LLM timeout:             {llm_timeout:.1f}s")

    print(f"LLM configured retries:  {llm_retries}")

    print(f"Estimated sequential:    {estimated_sequential_budget:.1f}s")

    print(f"Overall RAG timeout:     {overall_timeout:.1f}s")

    print()

    if overall_timeout <= 0:
        raise RuntimeError("RAG_REQUEST_TIMEOUT_SECONDS must be greater than zero.")

    if qdrant_timeout >= overall_timeout:
        raise RuntimeError("Qdrant timeout must be lower than the overall RAG timeout.")

    if llm_timeout >= overall_timeout:
        raise RuntimeError("LLM timeout must be lower than the overall RAG timeout.")

    if estimated_sequential_budget >= overall_timeout:
        print(
            "WARN: configured downstream "
            "timeouts/retries could consume "
            "the entire RAG request budget."
        )

        print(
            "This is acceptable temporarily "
            "for measurement, but Step 34 "
            "should use benchmark results to "
            "tighten the dependency budgets."
        )
    else:
        print("Dependency timeout budget fits inside overall RAG timeout.")

    print()
    print("RESULT: PASS")


if __name__ == "__main__":
    main()
