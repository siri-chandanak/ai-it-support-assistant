from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.observability.tracing import configure_tracing

_tracing_configured = False
_httpx_instrumented = False


def configure_api_observability(app: FastAPI) -> None:
    global _tracing_configured
    global _httpx_instrumented

    settings = get_settings()

    if not settings.otel_enabled:
        return

    if not _tracing_configured:
        configure_tracing(
            service_name=settings.otel_service_name,
            environment=settings.otel_environment,
            endpoint=settings.otel_exporter_otlp_endpoint,
        )
        _tracing_configured = True

    if not _httpx_instrumented:
        HTTPXClientInstrumentor().instrument()
        _httpx_instrumented = True

    FastAPIInstrumentor.instrument_app(app)
