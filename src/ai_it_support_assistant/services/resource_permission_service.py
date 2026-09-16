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


def create_resource_permission(
    *,
    session: Session,
    username: str,
    permission: str,
    resource_type: str,
    resource_value: str,
) -> ResourcePermissionModel:
    statement = select(ResourcePermissionModel).where(
        ResourcePermissionModel.username == username,
        ResourcePermissionModel.permission == permission,
        ResourcePermissionModel.resource_type == resource_type,
        ResourcePermissionModel.resource_value == resource_value,
    )

    existing_permission = session.execute(statement).scalar_one_or_none()

    if existing_permission is not None:
        return existing_permission

    resource_permission = ResourcePermissionModel(
        username=username,
        permission=permission,
        resource_type=resource_type,
        resource_value=resource_value,
    )

    session.add(resource_permission)
    session.commit()
    session.refresh(resource_permission)

    return resource_permission
