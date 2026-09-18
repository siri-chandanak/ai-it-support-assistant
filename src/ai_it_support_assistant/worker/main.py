from prometheus_client import start_http_server

from ai_it_support_assistant.core.config import (
    get_settings,
)
from ai_it_support_assistant.core.logging import (
    configure_logging,
)
from ai_it_support_assistant.observability.tracing import (
    configure_tracing,
)
from ai_it_support_assistant.worker.action_worker import (
    run_action_worker,
)


def main() -> None:
    settings = get_settings()

    configure_logging(
        log_level=settings.log_level,
    )

    if settings.otel_enabled:
        configure_tracing(
            service_name="ai-it-support-worker",
            environment=settings.otel_environment,
            endpoint=settings.otel_exporter_otlp_endpoint,
        )

    if not settings.action_worker_enabled:
        raise RuntimeError(
            "Action worker is disabled. Set ACTION_WORKER_ENABLED=true to start the worker."
        )

    if settings.metrics_enabled:
        start_http_server(
            settings.worker_metrics_port,
        )

    run_action_worker(
        settings=settings,
    )


if __name__ == "__main__":
    main()
