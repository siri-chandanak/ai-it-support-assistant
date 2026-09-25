import os
from collections.abc import Generator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from sqlalchemy.orm import Session

# ---------------------------------------------------------
# TEST ENVIRONMENT SETUP
#
# IMPORTANT:
# This must happen BEFORE importing application modules
# such as SessionLocal or app.
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(
    PROJECT_ROOT / ".env",
    override=False,
)

normal_database_url = os.getenv("DATABASE_URL")
test_database_url_value = os.getenv("TEST_DATABASE_URL")

if not test_database_url_value:
    raise RuntimeError("TEST_DATABASE_URL is not set. Use a separate PostgreSQL test database.")

is_github_actions = (
    os.getenv("GITHUB_ACTIONS", "")
    .strip()
    .lower()
    == "true"
)

allow_same_database_url = (
    os.getenv("ALLOW_TEST_DATABASE_URL_AS_DATABASE_URL", "").strip().lower() == "true"
)

if (
    test_database_url_value == normal_database_url
    and not is_github_actions
    and not allow_same_database_url
):
    raise RuntimeError(
        "TEST_DATABASE_URL must not equal DATABASE_URL "
        "outside GitHub Actions unless "
        "ALLOW_TEST_DATABASE_URL_AS_DATABASE_URL=true."
    )

os.environ["DATABASE_URL"] = test_database_url_value

os.environ["OTEL_ENABLED"] = "false"
os.environ["METRICS_ENABLED"] = "true"
os.environ["POLICY_PDP_MODE"] = "local"


# ---------------------------------------------------------
# APPLICATION IMPORTS
#
# These imports intentionally happen AFTER DATABASE_URL
# has been redirected to TEST_DATABASE_URL.
# ---------------------------------------------------------

from ai_it_support_assistant.api.dependencies.auth import (  # noqa: E402
    get_current_user,
)
from ai_it_support_assistant.db.session import SessionLocal  # noqa: E402
from ai_it_support_assistant.main import app  # noqa: E402
from ai_it_support_assistant.schemas.auth import User  # noqa: E402
from ai_it_support_assistant.schemas.policy import (  # noqa: E402
    PolicyContext,
    PolicyRequest,
    PolicyResource,
    PolicySubject,
)


@pytest.fixture
def span_exporter() -> Generator[InMemorySpanExporter, None, None]:
    exporter = InMemorySpanExporter()

    yield exporter

    exporter.clear()


@pytest.fixture
def test_tracer(
    span_exporter: InMemorySpanExporter,
):
    provider = TracerProvider()

    provider.add_span_processor(SimpleSpanProcessor(span_exporter))

    tracer = provider.get_tracer("ai_it_support_assistant.tests")

    yield tracer

    provider.force_flush()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    session = SessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin_auth_override() -> Generator[User, None, None]:
    admin_user = User(
        user_id=uuid4(),
        username="test-admin",
        roles=["admin"],
        disabled=False,
    )

    def override_get_current_user() -> User:
        return admin_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        yield admin_user
    finally:
        app.dependency_overrides.pop(
            get_current_user,
            None,
        )


@pytest.fixture
def reader_auth_override() -> Generator[User, None, None]:
    reader_user = User(
        user_id=uuid4(),
        username="test-reader",
        roles=["reader"],
        disabled=False,
    )

    def override_get_current_user() -> User:
        return reader_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        yield reader_user
    finally:
        app.dependency_overrides.pop(
            get_current_user,
            None,
        )


@pytest.fixture
def support_auth_override() -> Generator[User, None, None]:
    support_user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000020"),
        username="support",
        roles=["it_support"],
        disabled=False,
    )

    def override_get_current_user() -> User:
        return support_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        yield support_user
    finally:
        app.dependency_overrides.pop(
            get_current_user,
            None,
        )


@pytest.fixture
def test_database_url() -> str:
    database_url = os.getenv(
        "TEST_DATABASE_URL",
    )

    if not database_url:
        raise RuntimeError("TEST_DATABASE_URL is not set. Use a separate PostgreSQL test database.")

    return database_url


@pytest.fixture
def policy_request() -> PolicyRequest:
    return PolicyRequest(
        subject=PolicySubject(
            subject_id="alice",
            username="alice",
            roles=["it_support"],
            permissions=[
                "service-status:read",
            ],
            disabled=False,
        ),
        action="service_status.read",
        resource=PolicyResource(
            resource_type="service",
            resource_id="vpn-gateway",
            attributes={
                "service_name": "vpn-gateway",
            },
        ),
        context=PolicyContext(
            attributes={},
        ),
    )
