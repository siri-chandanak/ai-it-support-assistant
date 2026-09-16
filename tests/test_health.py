from fastapi.testclient import TestClient

from ai_it_support_assistant.main import app

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    # assert body == {"status": "healthy", "environment": "test", "version": "0.1.0"}
    assert body["status"] == "healthy"
    assert body["environment"] == "development"
    assert body["version"] == "0.1.0"


def test_readiness_does_not_check_opa_in_local_mode(
    client,
    monkeypatch,
) -> None:
    from ai_it_support_assistant.core.config import (
        get_settings,
    )

    settings = get_settings()

    monkeypatch.setattr(
        settings,
        "policy_pdp_mode",
        "local",
    )

    def should_not_be_called(**kwargs):
        raise AssertionError("OPA health should not be checked in local mode.")

    monkeypatch.setattr(
        "ai_it_support_assistant.api.routes.health.check_opa_health",
        should_not_be_called,
    )

    response = client.get("/api/v1/ready")

    assert response.status_code == 200


def test_readiness_returns_503_when_opa_unavailable(
    client,
    monkeypatch,
) -> None:
    from ai_it_support_assistant.core.config import (
        get_settings,
    )
    from ai_it_support_assistant.services.pdp.opa import (
        ExternalPDPUnavailableError,
    )

    settings = get_settings()

    monkeypatch.setattr(
        settings,
        "policy_pdp_mode",
        "opa",
    )

    def fake_check_opa_health(
        *,
        opa_url: str,
        timeout_seconds: float,
        require_bundle_ready: bool = False,
    ) -> None:
        raise ExternalPDPUnavailableError("OPA unavailable.")

    monkeypatch.setattr(
        "ai_it_support_assistant.api.routes.health.check_opa_health",
        fake_check_opa_health,
    )

    response = client.get("/api/v1/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Authorization service unavailable."}
