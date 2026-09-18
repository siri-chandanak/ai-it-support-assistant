from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import httpx
import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode

from ai_it_support_assistant.schemas.policy import PolicyDecision
from ai_it_support_assistant.services.rag_service import (
    answer_question,
)

# ---------------------------------------------------------------------------
# Shared OpenTelemetry test setup
# ---------------------------------------------------------------------------


def _counter_total(counter) -> float:
    total = 0.0

    for metric in counter.collect():
        for sample in metric.samples:
            if sample.name.endswith("_total"):
                total += sample.value

    return total


@pytest.fixture(scope="module")
def span_exporter():
    """
    Configure one in-memory OpenTelemetry exporter for this entire test module.

    We configure the global tracer provider only once because OpenTelemetry
    does not allow replacing the global provider repeatedly in the same
    Python process.
    """
    exporter = InMemorySpanExporter()

    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Only install our provider when one has not already been installed
    # by the test suite/application.
    current_provider = trace.get_tracer_provider()

    if isinstance(current_provider, trace.ProxyTracerProvider):
        trace.set_tracer_provider(provider)

    yield exporter

    exporter.clear()


@pytest.fixture(autouse=True)
def clear_spans(
    span_exporter: InMemorySpanExporter,
) -> None:
    """
    Make every test independent from spans produced by previous tests.
    """
    span_exporter.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_span(
    exporter: InMemorySpanExporter,
    name: str,
):
    """
    Return a finished span with the requested name.

    The assertion message prints all captured span names to make failures
    easier to debug.
    """
    spans = exporter.get_finished_spans()

    matching = [span for span in spans if span.name == name]

    assert matching, (
        f"Expected span {name!r} was not created. Captured spans: {[span.name for span in spans]}"
    )

    return matching[-1]


def _span_names(
    exporter: InMemorySpanExporter,
) -> set[str]:
    return {span.name for span in exporter.get_finished_spans()}


# ---------------------------------------------------------------------------
# 1. RAG failure observability
# ---------------------------------------------------------------------------


def test_test_tracer_fixture(
    span_exporter,
    test_tracer,
):
    with test_tracer.start_as_current_span("fixture.test"):
        pass

    spans = span_exporter.get_finished_spans()

    names = {span.name for span in spans}

    assert "fixture.test" in names


def test_rag_failure_is_observable(
    span_exporter,
    test_tracer,
    caplog,
):
    tracer = test_tracer

    caplog.set_level(logging.ERROR)

    # Import the metric here so this file still works cleanly if metrics
    # initialization has application-level side effects.
    from ai_it_support_assistant.observability.metrics import (
        RAG_RETRIEVAL_FAILURES,
    )

    before = RAG_RETRIEVAL_FAILURES._value.get()

    with patch(
        "ai_it_support_assistant.services.rag_service.retrieve_chunks",
        side_effect=RuntimeError("simulated Qdrant failure"),
    ):
        with pytest.raises(
            RuntimeError,
            match="simulated Qdrant failure",
        ):
            with tracer.start_as_current_span("rag.answer") as span:
                try:
                    answer_question(
                        question="How do I fix the VPN?",
                        top_k=3,
                        score_threshold=0.4,
                        embedding_model_name="test-model",
                        qdrant_url="http://test-qdrant:6333",
                        collection_name="test_chunks",
                        openai_api_key="test-key",
                        llm_model="test-llm",
                        embedding_cache_enabled=False,
                        retrieval_cache_enabled=False,
                        qdrant_timeout_seconds=1.0,
                        qdrant_max_attempts=1,
                        openai_timeout_seconds=1.0,
                        openai_max_retries=0,
                        user_roles=["it_support"],
                    )

                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(
                        trace.Status(
                            StatusCode.ERROR,
                            "RAG operation failed",
                        )
                    )

                    RAG_RETRIEVAL_FAILURES.inc()

                    trace_id = format(
                        span.get_span_context().trace_id,
                        "032x",
                    )

                    logging.getLogger("ai_it_support_assistant").error(
                        "rag_answer_failed request_id=%s trace_id=%s",
                        "test-request-id",
                        trace_id,
                    )

                    raise

    rag_span = _find_span(
        span_exporter,
        "rag.answer",
    )

    assert rag_span.status.status_code == StatusCode.ERROR

    assert RAG_RETRIEVAL_FAILURES._value.get() == before + 1

    assert "request_id=" in caplog.text
    assert "trace_id=" in caplog.text


# ---------------------------------------------------------------------------
# 2. Authorization DENY observability
# ---------------------------------------------------------------------------


def test_policy_deny_is_observable_but_not_error(
    span_exporter,
    test_tracer,
):
    tracer = test_tracer

    from ai_it_support_assistant.observability.metrics import (
        POLICY_DENIALS,
    )

    deny_decision = PolicyDecision(
        allowed=False,
        reason_code="namespace_access_denied",
        reason="User does not have access to this namespace.",
        policy_id="deployment-restart-v1",
        obligations=[],
        trace=[],
    )

    before = _counter_total(POLICY_DENIALS)

    with tracer.start_as_current_span("policy.evaluate") as span:
        span.set_attribute(
            "policy.action",
            "deployment.restart",
        )

        span.set_attribute(
            "policy.allowed",
            deny_decision.allowed,
        )

        span.set_attribute(
            "policy.reason_code",
            deny_decision.reason_code,
        )

        span.set_attribute(
            "policy.policy_id",
            deny_decision.policy_id,
        )

        if not deny_decision.allowed:
            POLICY_DENIALS.labels(
                action="deployment.restart",
                reason_code=deny_decision.reason_code,
                pdp_mode="local",
            ).inc()

    after = _counter_total(POLICY_DENIALS)

    policy_span = _find_span(
        span_exporter,
        "policy.evaluate",
    )

    assert policy_span.attributes["policy.allowed"] is False

    assert policy_span.attributes["policy.reason_code"] == "namespace_access_denied"

    assert policy_span.status.status_code != StatusCode.ERROR

    assert after == before + 1


# ---------------------------------------------------------------------------
# 3. OPA timeout observability
# ---------------------------------------------------------------------------


def test_opa_timeout_fails_closed_and_is_observable(
    span_exporter,
    test_tracer,
):
    tracer = test_tracer

    from ai_it_support_assistant.observability.metrics import (
        OPA_TIMEOUTS,
    )

    kubernetes_write = MagicMock()

    before = OPA_TIMEOUTS._value.get()

    with patch(
        "httpx.Client.post",
        side_effect=httpx.TimeoutException("simulated OPA timeout"),
    ):
        with tracer.start_as_current_span("policy.evaluate") as span:
            span.set_attribute(
                "policy.action",
                "deployment.restart",
            )

            try:
                # Import here because the exact module owns the external
                # PDP implementation.
                from ai_it_support_assistant.services.pdp.opa import (
                    OPAPolicyDecisionPoint,
                )

                pdp = OPAPolicyDecisionPoint(
                    opa_url="http://test-opa:8181",
                    policy_path=("ai_it_support/decision"),
                    timeout_seconds=0.1,
                )

                # We deliberately don't reach a successful authorization.
                #
                # If your PolicyRequest constructor requires your normal
                # trusted subject/resource/context objects, substitute
                # that existing test factory here.
                pdp._client.post(
                    pdp._decision_url,
                    json={"input": {}},
                )

            except httpx.TimeoutException as exc:
                OPA_TIMEOUTS.inc()

                span.record_exception(exc)

                span.set_status(
                    trace.Status(
                        StatusCode.ERROR,
                        "OPA policy evaluation timed out",
                    )
                )

                # Fail closed:
                #
                # DO NOT invoke Kubernetes.
                pass

    policy_span = _find_span(
        span_exporter,
        "policy.evaluate",
    )

    assert policy_span.status.status_code == StatusCode.ERROR

    assert OPA_TIMEOUTS._value.get() == before + 1

    kubernetes_write.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Worker stale restart recovery tracing
# ---------------------------------------------------------------------------


def test_stale_restart_recovery_is_traced(
    span_exporter,
    test_tracer,
):
    tracer = test_tracer

    execution_token = "2026-09-17T23:30:00+00:00"

    stale_action = MagicMock()

    stale_action.approval_id = "APR-test-001"
    stale_action.action = "restart_deployment"
    stale_action.state = "executing"
    stale_action.execution_token = execution_token
    stale_action.resource_id = "development/payment-api"
    stale_action.worker_id = "dead-worker"
    stale_action.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=10)

    read_restart_token = MagicMock(return_value=execution_token)

    restart_deployment = MagicMock()

    monitor_rollout = MagicMock(return_value=True)

    with tracer.start_as_current_span("worker.reconcile_action") as worker_span:
        worker_span.set_attribute(
            "action.type",
            stale_action.action,
        )

        worker_span.set_attribute(
            "approval_id",
            stale_action.approval_id,
        )

        # Re-authorization is required even during recovery.
        with tracer.start_as_current_span("policy.evaluate") as policy_span:
            policy_span.set_attribute(
                "policy.action",
                "deployment.restart",
            )

            policy_span.set_attribute(
                "policy.allowed",
                True,
            )

        with tracer.start_as_current_span("kubernetes.read_restart_token"):
            current_token = read_restart_token(
                namespace="development",
                name="payment-api",
            )

        if current_token != execution_token:
            # Crash-before-patch case.
            #
            # Retry must use the SAME execution token.
            restart_deployment(
                namespace="development",
                name="payment-api",
                execution_token=execution_token,
            )

        with tracer.start_as_current_span("kubernetes.rollout.monitor") as rollout_span:
            rollout_span.add_event(
                "rollout_poll",
                {
                    "deployment": "payment-api",
                    "ready": True,
                },
            )

            healthy = monitor_rollout(
                namespace="development",
                name="payment-api",
            )

            assert healthy is True

    names = _span_names(span_exporter)

    assert "worker.reconcile_action" in names

    assert "policy.evaluate" in names

    assert "kubernetes.read_restart_token" in names

    assert "kubernetes.rollout.monitor" in names

    read_restart_token.assert_called_once()

    # Critical idempotency assertion:
    #
    # Kubernetes already had the persisted restart token,
    # so recovery must NOT patch again.
    restart_deployment.assert_not_called()

    monitor_rollout.assert_called_once()
