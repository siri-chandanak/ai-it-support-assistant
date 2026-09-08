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


if __name__ == "__main__":
    main()
