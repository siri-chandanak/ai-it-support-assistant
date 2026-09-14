from uuid import UUID

from mcp.server.auth.middleware.auth_context import (
    get_access_token,
)

from ai_it_support_assistant.db.session import SessionLocal
from ai_it_support_assistant.repositories.user_repository import (
    get_user_by_id,
)
from ai_it_support_assistant.schemas.auth import User


class MCPAuthenticationError(Exception):
    pass


def get_mcp_current_user() -> User:
    token = get_access_token()

    if token is None:
        raise MCPAuthenticationError("Authentication required.")

    if not token.subject:
        raise MCPAuthenticationError("Authenticated subject missing.")

    try:
        user_id = UUID(token.subject)
    except ValueError as exc:
        raise MCPAuthenticationError("Authenticated subject is invalid.") from exc

    with SessionLocal() as db:
        user = get_user_by_id(
            db=db,
            user_id=user_id,
        )

        if user is None:
            raise MCPAuthenticationError("Authenticated user does not exist.")

        if user.disabled:
            raise MCPAuthenticationError("User is disabled.")

        return User(
            user_id=user.id,
            username=user.username,
            roles=user.roles,
            disabled=user.disabled,
        )
