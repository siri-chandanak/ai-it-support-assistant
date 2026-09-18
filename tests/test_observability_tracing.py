from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)


def create_test_tracer():
    exporter = InMemorySpanExporter()

    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    tracer = provider.get_tracer("ai_it_support_assistant.tests")

    return tracer, exporter


def test_rag_answer_span_is_created():
    tracer, exporter = create_test_tracer()

    with tracer.start_as_current_span("rag.answer"):
        pass

    spans = exporter.get_finished_spans()

    assert len(spans) == 1
    assert spans[0].name == "rag.answer"


def test_agent_route_records_safe_attribute():
    tracer, exporter = create_test_tracer()

    with tracer.start_as_current_span("agent.route") as span:
        span.set_attribute(
            "agent.action",
            "rag",
        )

    spans = exporter.get_finished_spans()

    assert spans[0].attributes["agent.action"] == "rag"


def test_question_is_not_recorded_in_span_attributes():
    tracer, exporter = create_test_tracer()

    secret_question = "show me confidential production credentials"

    with tracer.start_as_current_span("rag.answer") as span:
        span.set_attribute(
            "rag.source_count",
            2,
        )

    spans = exporter.get_finished_spans()

    serialized = str(spans[0].attributes)

    assert secret_question not in serialized
