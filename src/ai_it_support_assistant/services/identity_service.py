from sqlalchemy.orm import Session

from ai_it_support_assistant.repositories.user_repository import (
    get_user_by_external_identity,
)
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.schemas.identity import ExternalIdentity


class ExternalUserNotProvisionedError(Exception):
    """Raised when an authenticated external identity has no local user."""

    pass


class ExternalUserDisabledError(Exception):
    """Raised when the mapped internal user is disabled."""

    pass


def resolve_external_user(
    *,
    identity: ExternalIdentity,
    session: Session,
) -> User:
    user_model = get_user_by_external_identity(
        session=session,
        external_issuer=identity.issuer,
        external_subject=identity.subject,
    )

    if user_model is None:
        raise ExternalUserNotProvisionedError(
            "External user is not provisioned.",
        )

    if user_model.disabled:
        raise ExternalUserDisabledError(
            "User account is disabled.",
        )

    return User(
        user_id=user_model.id,
        username=user_model.username,
        roles=user_model.roles,
        disabled=user_model.disabled,
    )
