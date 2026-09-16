from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_it_support_assistant.models.resource_permission import (
    ResourcePermissionModel,
)


def has_resource_permission(
    *,
    session: Session,
    username: str,
    permission: str,
    resource_type: str,
    resource_value: str,
) -> bool:
    statement = select(ResourcePermissionModel.permission_id).where(
        ResourcePermissionModel.username == username,
        ResourcePermissionModel.permission == permission,
        ResourcePermissionModel.resource_type == resource_type,
        ResourcePermissionModel.resource_value == resource_value,
    )

    permission_id = session.scalar(statement)

    return permission_id is not None
