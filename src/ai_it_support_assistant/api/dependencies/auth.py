from collections.abc import Callable
from typing import Annotated

from fastapi import (
    Depends,
    HTTPException,
    status,
)
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from ai_it_support_assistant.core.config import (
    Settings,
    get_settings,
)
from ai_it_support_assistant.db.session import (
    get_db,
)
from ai_it_support_assistant.repositories.user_repository import (
    get_user_by_id,
)
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.services.auth_service import (
    AuthenticationError,
    decode_access_token,
)
from ai_it_support_assistant.services.oidc_authentication_service import (
    OIDCAuthorizationError,
    authenticate_oidc_user,
)
from ai_it_support_assistant.services.oidc_token_service import (
    OIDCAuthenticationError,
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def get_current_user(
    token: Annotated[
        str,
        Depends(oauth2_scheme),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
) -> User:
    settings = get_settings()

    try:
        token_data = decode_access_token(
            token=token,
            secret_key=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=(status.HTTP_401_UNAUTHORIZED),
            detail=("Invalid or expired authentication token."),
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from exc

    if token_data.user_id is None:
        raise HTTPException(
            status_code=(status.HTTP_401_UNAUTHORIZED),
            detail="Invalid authentication token.",
        )

    db_user = get_user_by_id(
        db,
        token_data.user_id,
    )

    if db_user is None:
        raise HTTPException(
            status_code=(status.HTTP_401_UNAUTHORIZED),
            detail="User no longer exists.",
        )

    if db_user.disabled:
        raise HTTPException(
            status_code=(status.HTTP_401_UNAUTHORIZED),
            detail="User account is disabled.",
        )

    return User(
        user_id=db_user.id,
        username=db_user.username,
        roles=db_user.roles,
        disabled=db_user.disabled,
    )


def require_role(
    required_role: str,
) -> Callable:
    def dependency(
        current_user: Annotated[
            User,
            Depends(get_current_user),
        ],
    ) -> User:
        if required_role not in current_user.roles:
            raise HTTPException(
                status_code=(status.HTTP_403_FORBIDDEN),
                detail=("Insufficient permissions."),
            )

        return current_user

    return dependency


def get_demo_current_user(
    *,
    token: str,
    db: Session,
) -> User:
    settings = get_settings()

    try:
        token_data = decode_access_token(
            token=token,
            secret_key=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from exc

    if token_data.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )

    db_user = get_user_by_id(
        db,
        token_data.user_id,
    )

    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists.",
        )

    if db_user.disabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled.",
        )

    return User(
        user_id=db_user.id,
        username=db_user.username,
        roles=db_user.roles,
        disabled=db_user.disabled,
    )


def get_oidc_current_user(
    *,
    token: str,
    db: Session,
    settings: Settings,
) -> User:
    try:
        return authenticate_oidc_user(
            token=token,
            settings=settings,
            session=db,
        )

    except OIDCAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from exc

    except OIDCAuthorizationError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not authorized.",
        ) from exc
