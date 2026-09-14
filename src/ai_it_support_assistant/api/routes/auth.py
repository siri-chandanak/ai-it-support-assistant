from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from fastapi.security import (
    OAuth2PasswordRequestForm,
)
from sqlalchemy.orm import Session

from ai_it_support_assistant.api.dependencies.auth import (
    get_current_user,
)
from ai_it_support_assistant.core.config import (
    Settings,
    get_settings,
)
from ai_it_support_assistant.db.session import (
    get_db,
)
from ai_it_support_assistant.schemas.auth import (
    TokenResponse,
    User,
)
from ai_it_support_assistant.services.auth_service import (
    AuthenticationError,
    authenticate_user,
    create_access_token,
)

router = APIRouter()


@router.post(
    "/auth/token",
    response_model=TokenResponse,
)
def login(
    form_data: Annotated[
        OAuth2PasswordRequestForm,
        Depends(),
    ],
    db: Annotated[
        Session,
        Depends(get_db),
    ],
    settings: Annotated[
        Settings,
        Depends(get_settings),
    ],
) -> TokenResponse:
    if settings.auth_mode == "oidc":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Local authentication is unavailable.",
        )

    if settings.auth_mode != "demo":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unsupported authentication mode.",
        )

    try:
        user = authenticate_user(
            db=db,
            username=form_data.username,
            password=form_data.password,
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from exc

    access_token = create_access_token(
        user=user,
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        expire_minutes=(settings.access_token_expire_minutes),
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
    )


@router.get(
    "/auth/me",
    response_model=User,
)
def get_me(
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
) -> User:
    return current_user
