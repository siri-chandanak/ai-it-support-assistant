from sqlalchemy.orm import Session

from ai_it_support_assistant.repositories.resource_permission_repository import (
    user_has_resource_permission,
)
from ai_it_support_assistant.schemas.auth import User


class ResourcePermissionDeniedError(Exception):
    pass


def require_resource_permission(
    *,
    user: User,
    permission: str,
    resource_type: str,
    resource_value: str,
    session: Session,
) -> None:
    allowed = user_has_resource_permission(
        session=session,
        username=user.username,
        permission=permission,
        resource_type=resource_type,
        resource_value=resource_value,
    )

    if not allowed:
        raise ResourcePermissionDeniedError(
            "Required resource permission missing.",
        )


def require_namespace_permission(
    *,
    user: User,
    permission: str,
    namespace: str,
    session: Session,
) -> None:
    require_resource_permission(
        user=user,
        permission=permission,
        resource_type="namespace",
        resource_value=namespace,
        session=session,
    )
