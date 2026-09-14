from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.services.permission_service import (
    PermissionDeniedError,
    require_permission,
)


class ToolAuthorizationError(Exception):
    pass


TOOL_ALLOWED_ROLES: dict[str, set[str]] = {
    "live_status": {
        "it_support",
        "admin",
    },
    "kubernetes_state": {
        "it_support",
        "admin",
    },
    "create_incident": {
        "it_support",
        "admin",
    },
    "restart_deployment": {
        "admin",
    },
}

TOOL_PERMISSION: dict[str, str] = {
    "live_status": "service-status:read",
    "kubernetes_state": "kubernetes:read",
    "create_incident": "incident:create",
    "restart_deployment": "deployment:restart",
}


def authorize_tool(
    *,
    tool_name: str,
    user: User,
) -> None:
    permission = TOOL_PERMISSION.get(
        tool_name,
    )

    if permission is None:
        raise ToolAuthorizationError(f"Unknown tool: {tool_name}")

    if user.disabled:
        raise ToolAuthorizationError("Disabled users cannot execute tools.")

    try:
        require_permission(
            user=user,
            permission=permission,
        )
    except PermissionDeniedError as exc:
        raise ToolAuthorizationError(
            f"User is not authorized to execute tool: {tool_name}"
        ) from exc
