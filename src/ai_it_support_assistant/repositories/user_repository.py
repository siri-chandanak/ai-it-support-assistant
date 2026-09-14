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


def get_user_by_external_identity(
    *,
    session: Session,
    external_issuer: str,
    external_subject: str,
) -> UserModel | None:
    statement = select(UserModel).where(
        UserModel.external_issuer == external_issuer,
        UserModel.external_subject == external_subject,
    )

    return session.scalar(statement)
