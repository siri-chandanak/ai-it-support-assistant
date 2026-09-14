import pytest
from sqlalchemy.exc import IntegrityError

from ai_it_support_assistant.repositories.resource_permission_repository import (
    create_resource_permission,
    delete_resource_permission,
    user_has_resource_permission,
)


def test_user_has_resource_permission(
    db_session,
) -> None:
    create_resource_permission(
        session=db_session,
        username="alice",
        permission="deployment:restart",
        resource_type="namespace",
        resource_value="team-a-dev",
    )

    assert user_has_resource_permission(
        session=db_session,
        username="alice",
        permission="deployment:restart",
        resource_type="namespace",
        resource_value="team-a-dev",
    )


def test_resource_permission_does_not_match_other_namespace(
    db_session,
) -> None:
    create_resource_permission(
        session=db_session,
        username="alice",
        permission="deployment:restart",
        resource_type="namespace",
        resource_value="team-a-dev",
    )

    assert not user_has_resource_permission(
        session=db_session,
        username="alice",
        permission="deployment:restart",
        resource_type="namespace",
        resource_value="team-b-dev",
    )


def test_resource_permission_does_not_match_other_user(
    db_session,
) -> None:
    create_resource_permission(
        session=db_session,
        username="alice",
        permission="deployment:restart",
        resource_type="namespace",
        resource_value="team-a-dev",
    )

    assert not user_has_resource_permission(
        session=db_session,
        username="bob",
        permission="deployment:restart",
        resource_type="namespace",
        resource_value="team-a-dev",
    )


def test_resource_permission_is_permission_specific(
    db_session,
) -> None:
    create_resource_permission(
        session=db_session,
        username="alice",
        permission="kubernetes:read",
        resource_type="namespace",
        resource_value="team-a-dev",
    )

    assert not user_has_resource_permission(
        session=db_session,
        username="alice",
        permission="deployment:restart",
        resource_type="namespace",
        resource_value="team-a-dev",
    )


def test_duplicate_resource_permission_is_rejected(
    db_session,
) -> None:
    create_resource_permission(
        session=db_session,
        username="alice",
        permission="deployment:restart",
        resource_type="namespace",
        resource_value="team-a-dev",
    )

    with pytest.raises(
        IntegrityError,
    ):
        create_resource_permission(
            session=db_session,
            username="alice",
            permission="deployment:restart",
            resource_type="namespace",
            resource_value="team-a-dev",
        )

    db_session.rollback()


def test_delete_resource_permission(
    db_session,
) -> None:
    create_resource_permission(
        session=db_session,
        username="alice",
        permission="deployment:restart",
        resource_type="namespace",
        resource_value="team-a-dev",
    )

    deleted = delete_resource_permission(
        session=db_session,
        username="alice",
        permission="deployment:restart",
        resource_type="namespace",
        resource_value="team-a-dev",
    )

    assert deleted

    assert not user_has_resource_permission(
        session=db_session,
        username="alice",
        permission="deployment:restart",
        resource_type="namespace",
        resource_value="team-a-dev",
    )
