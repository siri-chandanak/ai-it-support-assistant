from functools import lru_cache

import jwt
from jwt import PyJWKClient


class OIDCAuthenticationError(Exception):
    pass


@lru_cache
def get_jwks_client(
    jwks_url: str,
) -> PyJWKClient:
    return PyJWKClient(jwks_url)


def decode_oidc_access_token(
    *,
    token: str,
    issuer: str,
    audience: str,
    jwks_url: str,
    algorithms: list[str],
) -> dict[str, object]:
    try:
        jwks_client = get_jwks_client(jwks_url)

        signing_key = jwks_client.get_signing_key_from_jwt(
            token,
        )

        return jwt.decode(
            token,
            signing_key.key,
            algorithms=algorithms,
            audience=audience,
            issuer=issuer,
        )

    except jwt.PyJWTError as exc:
        raise OIDCAuthenticationError(
            "Invalid access token.",
        ) from exc
