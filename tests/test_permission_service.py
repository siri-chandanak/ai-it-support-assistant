from uuid import UUID

import pytest

from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.services.permission_service import (
    PermissionDeniedError,
    get_user_permissions,
    require_permission,
)


def test_reader_gets_knowledge_read() -> None:
    permissions = get_user_permissions(
        ["reader"],
    )

    assert "knowledge:read" in permissions
    assert "kubernetes:read" not in permissions


def test_it_support_gets_incident_permission() -> None:
    permissions = get_user_permissions(
        ["it_support"],
    )

    assert "incident:create" in permissions
    assert "kubernetes:read" in permissions
    assert "deployment:restart" not in permissions


def test_admin_gets_restart_permission() -> None:
    permissions = get_user_permissions(
        ["admin"],
    )

    assert "deployment:restart" in permissions


def test_unknown_role_gets_no_permissions() -> None:
    permissions = get_user_permissions(
        ["unknown-role"],
    )

    assert permissions == set()


def test_require_permission_allows_valid_permission() -> None:
    user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000101"),
        username="support",
        roles=["it_support"],
    )
    require_permission(
        user=user,
        permission="incident:create",
    )


def test_require_permission_rejects_missing_permission() -> None:
    user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000102"),
        username="support",
        roles=["it_support"],
    )

    with pytest.raises(
        PermissionDeniedError,
    ):
        require_permission(
            user=user,
            permission="deployment:restart",
        )


def test_reader_gets_knowledge_read_permission() -> None:
    permissions = get_user_permissions(
        ["reader"],
    )

    assert "knowledge:read" in permissions


def test_reader_does_not_get_kubernetes_read_permission() -> None:
    permissions = get_user_permissions(
        ["reader"],
    )

    assert "kubernetes:read" not in permissions


def test_it_support_gets_expected_permissions() -> None:
    permissions = get_user_permissions(
        ["it_support"],
    )

    assert "knowledge:read" in permissions
    assert "service-status:read" in permissions
    assert "kubernetes:read" in permissions
    assert "incident:create" in permissions
    assert "action:read" in permissions


def test_it_support_does_not_get_restart_permission() -> None:
    permissions = get_user_permissions(
        ["it_support"],
    )

    assert "deployment:restart" not in permissions


def test_multiple_roles_combine_permissions() -> None:
    permissions = get_user_permissions(
        [
            "reader",
            "it_support",
        ],
    )

    assert "knowledge:read" in permissions
    assert "service-status:read" in permissions
    assert "kubernetes:read" in permissions
    assert "incident:create" in permissions
    assert "action:read" in permissions


def test_require_permission_allows_authorized_user() -> None:
    user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000105"),
        username="support",
        roles=["it_support"],
    )

    require_permission(
        user=user,
        permission="incident:create",
    )


def test_require_permission_rejects_unauthorized_user() -> None:
    user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000107"),
        username="support",
        roles=["it_support"],
    )

    with pytest.raises(
        PermissionDeniedError,
    ):
        require_permission(
            user=user,
            permission="deployment:restart",
        )
