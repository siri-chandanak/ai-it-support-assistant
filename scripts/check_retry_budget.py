from ai_it_support_assistant.core.config import (
    get_settings,
)


def main() -> None:
    settings = get_settings()

    timeout = settings.qdrant_timeout_seconds

    attempts = settings.qdrant_max_attempts

    worst_case_without_backoff = timeout * attempts

    print("Qdrant Retry Budget")
    print("-------------------")
    print(f"Timeout per attempt: {timeout}s")
    print(f"Max attempts:        {attempts}")
    print(f"Worst case before backoff: {worst_case_without_backoff}s")

    if attempts > 3:
        print("WARN: high retry count can amplify overload.")


if __name__ == "__main__":
    main()
