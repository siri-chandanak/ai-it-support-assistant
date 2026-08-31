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
