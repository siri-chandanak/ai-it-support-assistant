from collections.abc import Generator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ai_it_support_assistant.api.dependencies.auth import (
    get_current_user,
)
from ai_it_support_assistant.db.session import SessionLocal
from ai_it_support_assistant.main import app
from ai_it_support_assistant.schemas.auth import User


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
def admin_auth_override() -> Generator[None, None, None]:
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
        yield
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def reader_auth_override() -> Generator[None, None, None]:
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
        yield
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def support_auth_override():
    support_user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000020"),
        username="support",
        roles=["it_support"],
    )

    def override_get_current_user() -> User:
        return support_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    yield support_user

    app.dependency_overrides.pop(
        get_current_user,
        None,
    )
