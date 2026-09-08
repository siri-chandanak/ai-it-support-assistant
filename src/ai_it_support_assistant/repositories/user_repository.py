from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_it_support_assistant.models.user import (
    UserModel,
)


def get_user_by_username(
    db: Session,
    username: str,
) -> UserModel | None:
    statement = select(UserModel).where(UserModel.username == username)

    return db.scalar(statement)


def get_user_by_id(
    db: Session,
    user_id: UUID,
) -> UserModel | None:
    return db.get(
        UserModel,
        user_id,
    )


def add_user(
    db: Session,
    user: UserModel,
) -> UserModel:
    db.add(user)
    db.commit()
    db.refresh(user)

    return user
