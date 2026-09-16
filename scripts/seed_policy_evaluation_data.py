from ai_it_support_assistant.db.session import (
    SessionLocal,
)
from ai_it_support_assistant.models.user import (
    UserModel,
)
from ai_it_support_assistant.repositories.user_repository import (
    add_user,
    get_user_by_username,
)
from ai_it_support_assistant.services.auth_service import (
    hash_password,
)
from ai_it_support_assistant.services.resource_permission_service import (
    create_resource_permission,
    has_resource_permission,
)


def create_demo_user(
    *,
    username: str,
    password: str,
    roles: list[str],
) -> None:
    with SessionLocal() as db:
        existing_user = get_user_by_username(
            db,
            username,
        )

        if existing_user is not None:
            print(f"user already exists: {username}")
            return

        user = UserModel(
            username=username,
            hashed_password=hash_password(password),
            roles=roles,
            disabled=False,
        )

        add_user(
            db,
            user,
        )

        print(f"user created: {username}")


def create_demo_permission(
    *,
    username: str,
    permission: str,
    resource_type: str,
    resource_value: str,
) -> None:
    with SessionLocal() as db:
        already_exists = has_resource_permission(
            session=db,
            username=username,
            permission=permission,
            resource_type=resource_type,
            resource_value=resource_value,
        )

        if already_exists:
            print(
                "permission already exists: "
                f"{username} "
                f"{permission} "
                f"{resource_type}="
                f"{resource_value}"
            )
            return

        create_resource_permission(
            session=db,
            username=username,
            permission=permission,
            resource_type=resource_type,
            resource_value=resource_value,
        )

        print(f"permission created: {username} {permission} {resource_type}={resource_value}")


def main() -> None:
    create_demo_user(
        username="reader",
        password="reader-pass",
        roles=["reader"],
    )

    create_demo_user(
        username="it-support",
        password="support-pass",
        roles=["it_support"],
    )

    create_demo_user(
        username="admin",
        password="admin-pass",
        roles=["admin"],
    )

    create_demo_permission(
        username="admin",
        permission="kubernetes:read",
        resource_type="namespace",
        resource_value="team-a-dev",
    )

    create_demo_permission(
        username="admin",
        permission="deployment:restart",
        resource_type="namespace",
        resource_value="team-a-dev",
    )

    create_demo_permission(
        username="it-support",
        permission="kubernetes:read",
        resource_type="namespace",
        resource_value="team-a-dev",
    )

    create_demo_permission(
        username="it-support",
        permission="deployment:restart",
        resource_type="namespace",
        resource_value="team-a-dev",
    )

    create_demo_permission(
        username="alice",
        permission="kubernetes:read",
        resource_type="namespace",
        resource_value="team-a-dev",
    )

    create_demo_permission(
        username="alice",
        permission="deployment:restart",
        resource_type="namespace",
        resource_value="team-a-dev",
    )


if __name__ == "__main__":
    main()
