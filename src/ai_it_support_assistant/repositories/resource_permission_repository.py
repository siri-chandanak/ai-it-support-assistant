from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ai_it_support_assistant.models.resource_permission import (
    ResourcePermissionModel,
)


def create_resource_permission(
    *,
    session: Session,
    username: str,
    permission: str,
    resource_type: str,
    resource_value: str,
) -> ResourcePermissionModel:
    resource_permission = ResourcePermissionModel(
        username=username,
        permission=permission,
        resource_type=resource_type,
        resource_value=resource_value,
    )

    session.add(
        resource_permission,
    )

    session.flush()

    return resource_permission


def user_has_resource_permission(
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

    permission_id = session.scalar(
        statement,
    )

    return permission_id is not None


def delete_resource_permission(
    *,
    session: Session,
    username: str,
    permission: str,
    resource_type: str,
    resource_value: str,
) -> bool:
    statement = delete(ResourcePermissionModel).where(
        ResourcePermissionModel.username == username,
        ResourcePermissionModel.permission == permission,
        ResourcePermissionModel.resource_type == resource_type,
        ResourcePermissionModel.resource_value == resource_value,
    )

    result = session.execute(
        statement,
    )

    return bool(
        result.rowcount,
    )
