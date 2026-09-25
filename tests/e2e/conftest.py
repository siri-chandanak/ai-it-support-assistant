from collections.abc import Generator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from ai_it_support_assistant.core.config import Settings, get_settings
from ai_it_support_assistant.models.resource_permission import (
    ResourcePermissionModel,
)
from ai_it_support_assistant.models.user import UserModel

from .helpers import require_safe_e2e_environment


@pytest.fixture
def e2e_settings() -> Settings:
    settings = get_settings()

    require_safe_e2e_environment(settings)

    return settings


@pytest.fixture
def e2e_run_id() -> str:
    return f"e2e-{uuid4()}"


@pytest.fixture
def e2e_resource_tracker() -> Generator[list[tuple[str, str]], None, None]:
    created_resources: list[tuple[str, str]] = []

    try:
        yield created_resources
    finally:
        # Actual cleanup will be added as each E2E resource
        # type is introduced.
        created_resources.clear()


@pytest.fixture
def persisted_support_user(db_session):
    username = "support"

    user = db_session.scalar(select(UserModel).where(UserModel.username == username))

    if user is None:
        user = UserModel(
            id=UUID("00000000-0000-0000-0000-000000000020"),
            username=username,
            hashed_password=None,
            roles=["it_support"],
            disabled=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(user)
    else:
        user.roles = ["it_support"]
        user.disabled = False
        user.updated_at = datetime.now(UTC)

    permission = db_session.scalar(
        select(ResourcePermissionModel).where(
            ResourcePermissionModel.username == username,
            ResourcePermissionModel.permission == "kubernetes:read",
            ResourcePermissionModel.resource_type == "namespace",
            ResourcePermissionModel.resource_value == "ai-support",
        )
    )

    if permission is None:
        permission = ResourcePermissionModel(
            username=username,
            permission="kubernetes:read",
            resource_type="namespace",
            resource_value="ai-support",
        )
        db_session.add(permission)

    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture
def persisted_admin_user(db_session):
    username = "test-admin"

    user = db_session.scalar(select(UserModel).where(UserModel.username == username))

    if user is None:
        user = UserModel(
            id=UUID("00000000-0000-0000-0000-000000000010"),
            username=username,
            hashed_password=None,
            roles=["admin"],
            disabled=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(user)
    else:
        user.roles = ["admin"]
        user.disabled = False
        user.updated_at = datetime.now(UTC)

    permission = db_session.scalar(
        select(ResourcePermissionModel).where(
            ResourcePermissionModel.username == username,
            ResourcePermissionModel.permission == "deployment:restart",
            ResourcePermissionModel.resource_type == "namespace",
            ResourcePermissionModel.resource_value == "ai-support",
        )
    )

    if permission is None:
        permission = ResourcePermissionModel(
            username=username,
            permission="deployment:restart",
            resource_type="namespace",
            resource_value="ai-support",
        )
        db_session.add(permission)

    db_session.commit()
    db_session.refresh(user)

    return user
