from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from ai_it_support_assistant.repositories.user_repository import (
    get_user_by_username,
)
from ai_it_support_assistant.schemas.auth import (
    TokenData,
    User,
)

password_hash = PasswordHash.recommended()


class AuthenticationError(Exception):
    pass


def hash_password(
    password: str,
) -> str:
    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    return password_hash.verify(
        plain_password,
        hashed_password,
    )


def authenticate_user(
    *,
    db: Session,
    username: str,
    password: str,
) -> User:
    user = get_user_by_username(
        db,
        username,
    )

    if user is None:
        raise AuthenticationError("Invalid username or password.")

    if not verify_password(
        password,
        user.hashed_password,
    ):
        raise AuthenticationError("Invalid username or password.")

    if user.disabled:
        raise AuthenticationError("User account is disabled.")

    return User(
        user_id=user.id,
        username=user.username,
        roles=user.roles,
        disabled=user.disabled,
    )


def create_access_token(
    *,
    user: User,
    secret_key: str,
    algorithm: str,
    expire_minutes: int,
) -> str:
    expires_at = datetime.now(UTC) + timedelta(minutes=expire_minutes)

    payload = {
        "sub": str(user.user_id),
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        secret_key,
        algorithm=algorithm,
    )


def decode_access_token(
    *,
    token: str,
    secret_key: str,
    algorithm: str,
) -> TokenData:
    try:
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[algorithm],
        )

        subject = payload.get("sub")

        if not isinstance(subject, str):
            raise AuthenticationError("Invalid authentication token.")

        try:
            user_id = UUID(subject)
        except ValueError as exc:
            raise AuthenticationError("Invalid authentication token.") from exc

        return TokenData(
            user_id=user_id,
        )

    except InvalidTokenError as exc:
        raise AuthenticationError("Invalid authentication token.") from exc
