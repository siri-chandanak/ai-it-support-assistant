from fastapi.testclient import TestClient

from ai_it_support_assistant.core.config import Settings
from ai_it_support_assistant.main import app

client = TestClient(app)


def test_default_cors_origin_allows_local_frontend() -> None:
    settings = Settings()

    assert "http://localhost:3000" in settings.cors_allowed_origins


def test_local_frontend_origin_is_allowed() -> None:
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200

    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_unknown_origin_is_not_allowed() -> None:
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.headers.get("access-control-allow-origin") is None
