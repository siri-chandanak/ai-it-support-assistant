from ai_it_support_assistant.schemas.auth import User


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
}


def authorize_tool(
    *,
    tool_name: str,
    user: User,
) -> None:
    allowed_roles = TOOL_ALLOWED_ROLES.get(tool_name)

    if allowed_roles is None:
        raise ToolAuthorizationError("Unknown tool.")

    if not set(user.roles) & allowed_roles:
        raise ToolAuthorizationError("User is not authorized to use this tool.")
