VALID_ROLES = {
    "reader",
    "it_support",
    "admin",
}


class AuthorizationConfigurationError(Exception):
    pass


def validate_allowed_roles(
    roles: list[str],
) -> list[str]:
    normalized_roles = sorted(set(roles))

    if not normalized_roles:
        raise AuthorizationConfigurationError(
            "Document must allow at least one role."
        )

    invalid_roles = (
        set(normalized_roles)
        - VALID_ROLES
    )

    if invalid_roles:
        raise AuthorizationConfigurationError(
            "Document contains invalid roles."
        )

    return normalized_roles