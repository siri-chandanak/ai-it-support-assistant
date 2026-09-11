from ai_it_support_assistant.schemas.auth import User

VALID_ROLES = {
    "reader",
    "it_support",
    "admin",
}

TOOL_ALLOWED_ROLES: dict[str, set[str]] = {
    "create_incident": {
        "it_support",
        "admin",
    },
}


class ToolAuthorizationError(Exception):
    pass


class AuthorizationConfigurationError(Exception):
    pass


def validate_allowed_roles(
    roles: list[str],
) -> list[str]:
    normalized_roles = sorted(set(roles))

    if not normalized_roles:
        raise AuthorizationConfigurationError("Document must allow at least one role.")

    invalid_roles = set(normalized_roles) - VALID_ROLES

    if invalid_roles:
        raise AuthorizationConfigurationError("Document contains invalid roles.")

    return normalized_roles


def authorize_tool(
    *,
    tool_name: str,
    user: User,
) -> None:
    allowed_roles = TOOL_ALLOWED_ROLES.get(tool_name)

    if allowed_roles is None:
        raise ToolAuthorizationError(f"Unknown tool: {tool_name}")

    if user.disabled:
        raise ToolAuthorizationError("Disabled users cannot execute tools.")

    user_roles = set(user.roles)

    if not user_roles.intersection(allowed_roles):
        raise ToolAuthorizationError(f"User is not authorized to execute tool: {tool_name}")
