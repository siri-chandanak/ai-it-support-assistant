from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)


def test_counter_increments():
    registry = CollectorRegistry()

    counter = Counter(
        "test_requests_total",
        "Test request counter",
        registry=registry,
    )

    counter.inc()

    output = generate_latest(registry).decode()

    assert "test_requests_total 1.0" in output


def test_histogram_records_observation():
    registry = CollectorRegistry()

    histogram = Histogram(
        "test_duration_seconds",
        "Test duration",
        registry=registry,
    )

    histogram.observe(0.5)

    output = generate_latest(registry).decode()

    assert "test_duration_seconds_count 1.0" in output


def test_queue_depth_gauge_changes():
    registry = CollectorRegistry()

    gauge = Gauge(
        "test_action_queue_depth",
        "Test queue depth",
        registry=registry,
    )

    gauge.set(3)

    output = generate_latest(registry).decode()

    assert "test_action_queue_depth 3.0" in output


FORBIDDEN_METRIC_LABELS = {
    "username",
    "request_id",
    "trace_id",
    "approval_id",
    "incident_id",
}


def test_forbidden_high_cardinality_labels():
    metric_label_names = {
        "method",
        "route",
        "status_class",
        "action_type",
        "outcome",
        "reason_code",
        "pdp_mode",
    }

    assert FORBIDDEN_METRIC_LABELS.isdisjoint(metric_label_names)
