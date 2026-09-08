from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from ai_it_support_assistant.api.dependencies.auth import (
    get_current_user,
)
from ai_it_support_assistant.main import app
from ai_it_support_assistant.schemas.auth import User


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
