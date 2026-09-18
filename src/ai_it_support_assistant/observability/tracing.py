from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def configure_tracing(
    *,
    service_name: str,
    environment: str,
    endpoint: str,
) -> None:
    resource = Resource.create(
        {
            "service.name": service_name,
            "deployment.environment.name": environment,
        }
    )

    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(
        endpoint=endpoint,
        insecure=True,
    )

    provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)


def get_tracer():
    return trace.get_tracer("ai_it_support_assistant")


def get_current_trace_id() -> str | None:
    span = trace.get_current_span()
    context = span.get_span_context()

    if not context.is_valid:
        return None

    return format(context.trace_id, "032x")


def get_current_span_id() -> str | None:
    span = trace.get_current_span()
    context = span.get_span_context()

    if not context.is_valid:
        return None

    return format(context.span_id, "016x")
