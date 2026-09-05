import logging

from ai_it_support_assistant.core.request_context import (
    get_request_id,
    request_id_context,
)


def test_request_logs_completion(
    client,
    caplog,
) -> None:
    with caplog.at_level(logging.INFO):
        response = client.get(
            "/api/v1/health",
            headers={"X-Request-ID": "test-123"},
        )

    assert response.status_code == 200

    assert any(
        ("request_completed" in record.message and "test-123" in record.message)
        for record in caplog.records
    )


def test_request_id_context() -> None:
    token = request_id_context.set("request-abc")

    try:
        assert get_request_id() == "request-abc"
    finally:
        request_id_context.reset(token)


def test_response_contains_request_id(
    client,
) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers


def test_existing_request_id_is_preserved(
    client,
) -> None:
    response = client.get(
        "/api/v1/health",
        headers={"X-Request-ID": "test-request-123"},
    )

    assert response.headers["X-Request-ID"] == "test-request-123"


def test_generated_request_ids_are_unique(
    client,
) -> None:
    response_one = client.get("/api/v1/health")

    response_two = client.get("/api/v1/health")

    assert response_one.headers["X-Request-ID"] != response_two.headers["X-Request-ID"]
