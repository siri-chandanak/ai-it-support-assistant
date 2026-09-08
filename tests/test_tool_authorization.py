from uuid import UUID

import pytest

from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.services.tool_authorization_service import (
    ToolAuthorizationError,
    authorize_tool,
)


def test_it_support_can_use_live_status() -> None:
    user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        username="support",
        roles=["it_support"],
    )

    authorize_tool(
        tool_name="live_status",
        user=user,
    )


def test_admin_can_use_live_status() -> None:
    user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000003"),
        username="admin",
        roles=["admin"],
    )

    authorize_tool(
        tool_name="live_status",
        user=user,
    )


def test_reader_cannot_use_live_status() -> None:
    user = User(
        user_id=UUID("00000000-0000-0000-0000-000000000002"),
        username="reader",
        roles=["reader"],
    )

    with pytest.raises(ToolAuthorizationError):
        authorize_tool(
            tool_name="live_status",
            user=user,
        )
