from uuid import uuid4

import pytest

from ai_it_support_assistant.repositories.resource_permission_repository import (
    create_resource_permission,
)
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.services.resource_authorization_service import (
    ResourcePermissionDeniedError,
    require_namespace_permission,
)


def test_require_namespace_permission_allows_grant(
    db_session,
) -> None:
    user = User(
        user_id=uuid4(),
        username="alice",
        roles=["admin"],
        disabled=False,
    )

    create_resource_permission(
        session=db_session,
        username="alice",
        permission="deployment:restart",
        resource_type="namespace",
        resource_value="team-a-dev",
    )

    require_namespace_permission(
        user=user,
        permission="deployment:restart",
        namespace="team-a-dev",
        session=db_session,
    )


def test_require_namespace_permission_denies_other_namespace(
    db_session,
) -> None:
    user = User(
        user_id=uuid4(),
        username="alice",
        roles=["admin"],
        disabled=False,
    )

    create_resource_permission(
        session=db_session,
        username="alice",
        permission="deployment:restart",
        resource_type="namespace",
        resource_value="team-a-dev",
    )

    with pytest.raises(
        ResourcePermissionDeniedError,
    ):
        require_namespace_permission(
            user=user,
            permission="deployment:restart",
            namespace="team-b-dev",
            session=db_session,
        )


def test_require_namespace_permission_denies_missing_grant(
    db_session,
) -> None:
    user = User(
        user_id=uuid4(),
        username="alice",
        roles=["admin"],
        disabled=False,
    )

    with pytest.raises(
        ResourcePermissionDeniedError,
    ):
        require_namespace_permission(
            user=user,
            permission="deployment:restart",
            namespace="team-a-dev",
            session=db_session,
        )


def test_kubernetes_read_allowed_for_granted_namespace(
    db_session,
) -> None:
    user = User(
        user_id=uuid4(),
        username="alice",
        roles=["it_support"],
        disabled=False,
    )

    create_resource_permission(
        session=db_session,
        username="alice",
        permission="kubernetes:read",
        resource_type="namespace",
        resource_value="team-a-dev",
    )

    require_namespace_permission(
        user=user,
        permission="kubernetes:read",
        namespace="team-a-dev",
        session=db_session,
    )


def test_kubernetes_read_denied_for_other_namespace(
    db_session,
) -> None:
    user = User(
        user_id=uuid4(),
        username="alice",
        roles=["it_support"],
        disabled=False,
    )

    create_resource_permission(
        session=db_session,
        username="alice",
        permission="kubernetes:read",
        resource_type="namespace",
        resource_value="team-a-dev",
    )

    with pytest.raises(
        ResourcePermissionDeniedError,
    ):
        require_namespace_permission(
            user=user,
            permission="kubernetes:read",
            namespace="finance-prod",
            session=db_session,
        )
