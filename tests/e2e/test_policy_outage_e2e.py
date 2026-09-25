from fastapi.testclient import TestClient

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.schemas.auth import User


def test_opa_outage_blocks_kubernetes_restart(
    client: TestClient,
    admin_auth_override: User,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "POLICY_PDP_MODE",
        "opa",
    )
    monkeypatch.setenv(
        "OPA_URL",
        "http://127.0.0.1:65530",
    )

    get_settings.cache_clear()

    try:
        settings = get_settings()

        assert settings.policy_pdp_mode == "opa"
        assert settings.opa_url == "http://127.0.0.1:65530"

        response = client.post(
            "/api/v1/agent/ask",
            json={
                "question": ("Restart restart-test deployment in namespace ai-support."),
            },
        )

        assert response.status_code == 503

        body = response.json()

        assert body.get("approval_id") is None

    finally:
        get_settings.cache_clear()
