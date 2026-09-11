from uuid import UUID

import pytest

from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.services.authorization_service import (
    ToolAuthorizationError,
    authorize_tool,
)


def test_it_support_can_create_incident() -> None:
    user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000021"),
        username="it-support",
        roles=["it_support"],
        disabled=False,
    )

    authorize_tool(
        tool_name="create_incident",
        user=user,
    )


def test_admin_can_create_incident() -> None:
    user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000022"),
        username="admin",
        roles=["admin"],
        disabled=False,
    )

    authorize_tool(
        tool_name="create_incident",
        user=user,
    )


def test_reader_cannot_create_incident() -> None:
    user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000023"),
        username="reader",
        roles=["reader"],
        disabled=False,
    )

    with pytest.raises(ToolAuthorizationError):
        authorize_tool(
            tool_name="create_incident",
            user=user,
        )


def test_disabled_user_cannot_create_incident() -> None:
    user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000024"),
        username="it-support",
        roles=["it_support"],
        disabled=True,
    )

    with pytest.raises(ToolAuthorizationError):
        authorize_tool(
            tool_name="create_incident",
            user=user,
        )


def test_unknown_tool_is_denied() -> None:
    user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000025"),
        username="admin",
        roles=["admin"],
        disabled=False,
    )

    with pytest.raises(ToolAuthorizationError):
        authorize_tool(
            tool_name="unknown_tool",
            user=user,
        )
