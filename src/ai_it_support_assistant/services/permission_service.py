from typing import Literal

from ai_it_support_assistant.schemas.auth import User

Permission = Literal[
    "knowledge:read",
    "service-status:read",
    "kubernetes:read",
    "incident:create",
    "deployment:restart",
    "action:read",
]

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "reader": {
        "knowledge:read",
    },
    "it_support": {
        "knowledge:read",
        "service-status:read",
        "kubernetes:read",
        "incident:create",
        "action:read",
    },
    "admin": {
        "knowledge:read",
        "service-status:read",
        "kubernetes:read",
        "incident:create",
        "deployment:restart",
        "action:read",
    },
}


class PermissionDeniedError(Exception):
    pass


def get_user_permissions(
    roles: list[str],
) -> set[str]:
    permissions: set[str] = set()

    for role in roles:
        permissions.update(
            ROLE_PERMISSIONS.get(
                role,
                set(),
            )
        )

    return permissions


def require_permission(
    *,
    user: User,
    permission: str,
) -> None:
    permissions = get_user_permissions(
        user.roles,
    )

    if permission not in permissions:
        raise PermissionDeniedError(
            "Required permission missing.",
        )
