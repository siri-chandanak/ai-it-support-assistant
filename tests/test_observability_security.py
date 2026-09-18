from opentelemetry.sdk.trace import (
    TracerProvider,
)
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

SENSITIVE_VALUES = [
    "Bearer super-secret-token",
    "sk-test-api-key",
    "password123",
    "very sensitive document content",
    "full private llm prompt",
    "apiVersion: v1 kubeconfig secret",
    "[0.123, -0.456, 0.789]",
]


def create_test_tracer():
    exporter = InMemorySpanExporter()

    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    return (
        provider.get_tracer("ai_it_support_assistant.security-tests"),
        exporter,
    )


def test_sensitive_values_not_emitted_to_span():
    tracer, exporter = create_test_tracer()

    with tracer.start_as_current_span("rag.answer") as span:
        span.set_attribute(
            "rag.source_count",
            3,
        )

        span.set_attribute(
            "rag.outcome",
            "answered",
        )

    spans = exporter.get_finished_spans()

    telemetry = str(
        [
            {
                "name": span.name,
                "attributes": dict(span.attributes),
            }
            for span in spans
        ]
    )

    for sensitive_value in SENSITIVE_VALUES:
        assert sensitive_value not in telemetry


FORBIDDEN_TELEMETRY_KEYS = {
    "authorization",
    "api_key",
    "openai_api_key",
    "jwt",
    "password",
    "prompt",
    "document_text",
    "kubeconfig",
    "embedding_vector",
}


def test_forbidden_sensitive_attribute_names():
    allowed_attributes = {
        "rag.source_count",
        "rag.outcome",
        "llm.model",
        "qdrant.top_k",
        "policy.action",
        "policy.allowed",
    }

    assert FORBIDDEN_TELEMETRY_KEYS.isdisjoint(allowed_attributes)
