import os

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_alembic_upgrade_creates_expected_tables() -> None:
    database_url = os.environ["TEST_DATABASE_URL"]

    engine = create_engine(
        database_url,
        isolation_level="AUTOCOMMIT",
    )

    with engine.connect() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))

    engine.dispose()

    config = Config("alembic.ini")
    config.set_main_option(
        "sqlalchemy.url",
        database_url.replace("%", "%%"),
    )

    command.upgrade(
        config,
        "head",
    )

    engine = create_engine(database_url)

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    assert {
        "users",
        "incidents",
        "pending_actions",
        "audit_events",
        "alembic_version",
    }.issubset(tables)

    engine.dispose()


def test_readiness_returns_ready_when_database_is_available(
    client,
    monkeypatch,
) -> None:
    def fake_check_database_health(*, database_url: str) -> None:
        assert database_url

    monkeypatch.setattr(
        "ai_it_support_assistant.api.routes.health.check_database_health",
        fake_check_database_health,
    )

    response = client.get("/api/v1/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_returns_503_when_database_is_unavailable(
    client,
    monkeypatch,
) -> None:
    from ai_it_support_assistant.services.database_health_service import (
        DatabaseHealthError,
    )

    def fake_check_database_health(*, database_url: str) -> None:
        raise DatabaseHealthError("Database health check failed.")

    monkeypatch.setattr(
        "ai_it_support_assistant.api.routes.health.check_database_health",
        fake_check_database_health,
    )

    response = client.get("/api/v1/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable."}
