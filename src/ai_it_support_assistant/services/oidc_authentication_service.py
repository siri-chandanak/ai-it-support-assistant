from sqlalchemy.orm import Session

from ai_it_support_assistant.core.config import Settings
from ai_it_support_assistant.identity.providers.generic_oidc import (
    OIDCClaimsMapper,
    OIDCClaimsMappingError,
)
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.services.identity_service import (
    ExternalUserDisabledError,
    ExternalUserNotProvisionedError,
    resolve_external_user,
)
from ai_it_support_assistant.services.oidc_token_service import (
    OIDCAuthenticationError,
    decode_oidc_access_token,
)


class OIDCAuthorizationError(Exception):
    pass


def authenticate_oidc_user(
    *,
    token: str,
    settings: Settings,
    session: Session,
) -> User:
    claims = decode_oidc_access_token(
        token=token,
        issuer=settings.oidc_issuer,
        audience=settings.oidc_audience,
        jwks_url=settings.oidc_jwks_url,
        algorithms=settings.oidc_algorithm_list,
    )

    try:
        identity = OIDCClaimsMapper().map_claims(
            claims,
        )
    except OIDCClaimsMappingError as exc:
        raise OIDCAuthenticationError(
            "Invalid OIDC identity claims.",
        ) from exc

    required_scope = settings.oidc_required_scope

    if required_scope and required_scope not in identity.scopes:
        raise OIDCAuthorizationError(
            "Required API scope is missing.",
        )

    try:
        return resolve_external_user(
            identity=identity,
            session=session,
        )
    except (
        ExternalUserNotProvisionedError,
        ExternalUserDisabledError,
    ) as exc:
        raise OIDCAuthorizationError(
            "External user is not authorized.",
        ) from exc
