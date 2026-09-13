from ai_it_support_assistant.core.config import (
    get_settings,
)
from ai_it_support_assistant.core.logging import (
    configure_logging,
)
from ai_it_support_assistant.worker.action_worker import (
    run_action_worker,
)


def main() -> None:
    settings = get_settings()

    configure_logging(
        log_level=settings.log_level,
    )

    if not settings.action_worker_enabled:
        raise RuntimeError(
            "Action worker is disabled. Set ACTION_WORKER_ENABLED=true to start the worker."
        )

    run_action_worker(
        settings=settings,
    )


if __name__ == "__main__":
    main()
