from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from ai_it_support_assistant.services import oidc_token_service
from ai_it_support_assistant.services.oidc_token_service import (
    OIDCAuthenticationError,
    decode_oidc_access_token,
)


@pytest.fixture
def rsa_key_pair():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    public_key = private_key.public_key()

    return private_key, public_key


def make_token(
    *,
    private_key,
    issuer: str = "https://idp.example.com",
    audience: str = "ai-it-support-api",
    subject: str = "user-123",
    expires_delta: timedelta = timedelta(minutes=5),
    kid: str = "test-key-1",
) -> str:
    now = datetime.now(UTC)

    payload = {
        "sub": subject,
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + expires_delta,
        "scp": "ai-support.access",
    }

    return jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={
            "kid": kid,
        },
    )


class FakeSigningKey:
    def __init__(self, key):
        self.key = key


class FakeJwksClient:
    def __init__(self, public_key):
        self.public_key = public_key

    def get_signing_key_from_jwt(self, token):
        return FakeSigningKey(
            self.public_key,
        )


class FakeUnknownKeyClient:
    def get_signing_key_from_jwt(
        self,
        token,
    ):
        raise jwt.PyJWKClientError("Unable to find a signing key.")


def test_decode_oidc_access_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signing_key = Mock()
    signing_key.key = "public-key"

    jwks_client = Mock()
    jwks_client.get_signing_key_from_jwt.return_value = signing_key

    monkeypatch.setattr(
        oidc_token_service,
        "get_jwks_client",
        lambda _url: jwks_client,
    )

    expected_claims = {
        "sub": "user-123",
        "iss": "https://idp.example.com",
    }

    decode_mock = Mock(
        return_value=expected_claims,
    )

    monkeypatch.setattr(
        oidc_token_service.jwt,
        "decode",
        decode_mock,
    )

    result = oidc_token_service.decode_oidc_access_token(
        token="example-token",
        issuer="https://idp.example.com",
        audience="ai-it-support-api",
        jwks_url="https://idp.example.com/jwks",
        algorithms=["RS256"],
    )

    assert result == expected_claims

    jwks_client.get_signing_key_from_jwt.assert_called_once_with(
        "example-token",
    )

    decode_mock.assert_called_once_with(
        "example-token",
        "public-key",
        algorithms=["RS256"],
        audience="ai-it-support-api",
        issuer="https://idp.example.com",
    )


def test_decode_oidc_access_token_rejects_invalid_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signing_key = Mock()
    signing_key.key = "public-key"

    jwks_client = Mock()
    jwks_client.get_signing_key_from_jwt.return_value = signing_key

    monkeypatch.setattr(
        oidc_token_service,
        "get_jwks_client",
        lambda _url: jwks_client,
    )

    def raise_invalid_token(*args, **kwargs):
        raise jwt.InvalidTokenError(
            "invalid token",
        )

    monkeypatch.setattr(
        oidc_token_service.jwt,
        "decode",
        raise_invalid_token,
    )

    with pytest.raises(oidc_token_service.OIDCAuthenticationError):
        oidc_token_service.decode_oidc_access_token(
            token="bad-token",
            issuer="https://idp.example.com",
            audience="ai-it-support-api",
            jwks_url="https://idp.example.com/jwks",
            algorithms=["RS256"],
        )


def test_decode_oidc_access_token_accepts_valid_token(
    monkeypatch,
    rsa_key_pair,
) -> None:
    private_key, public_key = rsa_key_pair

    token = make_token(
        private_key=private_key,
    )

    fake_client = FakeJwksClient(
        public_key,
    )

    monkeypatch.setattr(
        "ai_it_support_assistant.services.oidc_token_service.get_jwks_client",
        lambda jwks_url: fake_client,
    )

    claims = decode_oidc_access_token(
        token=token,
        issuer="https://idp.example.com",
        audience="ai-it-support-api",
        jwks_url="https://idp.example.com/jwks",
        algorithms=["RS256"],
    )

    assert claims["sub"] == "user-123"


def test_decode_oidc_access_token_rejects_wrong_issuer(
    monkeypatch,
    rsa_key_pair,
) -> None:
    private_key, public_key = rsa_key_pair

    token = make_token(
        private_key=private_key,
        issuer="https://wrong-idp.example.com",
    )

    fake_client = FakeJwksClient(
        public_key,
    )

    monkeypatch.setattr(
        "ai_it_support_assistant.services.oidc_token_service.get_jwks_client",
        lambda jwks_url: fake_client,
    )

    with pytest.raises(
        OIDCAuthenticationError,
    ):
        decode_oidc_access_token(
            token=token,
            issuer="https://idp.example.com",
            audience="ai-it-support-api",
            jwks_url="https://idp.example.com/jwks",
            algorithms=["RS256"],
        )


def test_decode_oidc_access_token_rejects_wrong_audience(
    monkeypatch,
    rsa_key_pair,
) -> None:
    private_key, public_key = rsa_key_pair

    token = make_token(
        private_key=private_key,
        audience="some-other-api",
    )

    fake_client = FakeJwksClient(
        public_key,
    )

    monkeypatch.setattr(
        "ai_it_support_assistant.services.oidc_token_service.get_jwks_client",
        lambda jwks_url: fake_client,
    )

    with pytest.raises(
        OIDCAuthenticationError,
    ):
        decode_oidc_access_token(
            token=token,
            issuer="https://idp.example.com",
            audience="ai-it-support-api",
            jwks_url="https://idp.example.com/jwks",
            algorithms=["RS256"],
        )


def test_decode_oidc_access_token_rejects_expired_token(
    monkeypatch,
    rsa_key_pair,
) -> None:
    private_key, public_key = rsa_key_pair

    token = make_token(
        private_key=private_key,
        expires_delta=timedelta(
            minutes=-5,
        ),
    )

    fake_client = FakeJwksClient(
        public_key,
    )

    monkeypatch.setattr(
        "ai_it_support_assistant.services.oidc_token_service.get_jwks_client",
        lambda jwks_url: fake_client,
    )

    with pytest.raises(
        OIDCAuthenticationError,
    ):
        decode_oidc_access_token(
            token=token,
            issuer="https://idp.example.com",
            audience="ai-it-support-api",
            jwks_url="https://idp.example.com/jwks",
            algorithms=["RS256"],
        )


def test_decode_oidc_access_token_rejects_tampered_signature(
    monkeypatch,
) -> None:
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    wrong_private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    wrong_public_key = wrong_private_key.public_key()

    token = make_token(
        private_key=private_key,
    )

    fake_client = FakeJwksClient(
        wrong_public_key,
    )

    monkeypatch.setattr(
        "ai_it_support_assistant.services.oidc_token_service.get_jwks_client",
        lambda jwks_url: fake_client,
    )

    with pytest.raises(
        OIDCAuthenticationError,
    ):
        decode_oidc_access_token(
            token=token,
            issuer="https://idp.example.com",
            audience="ai-it-support-api",
            jwks_url="https://idp.example.com/jwks",
            algorithms=["RS256"],
        )


def test_decode_oidc_access_token_rejects_unknown_signing_key(
    monkeypatch,
    rsa_key_pair,
) -> None:
    private_key, _ = rsa_key_pair

    token = make_token(
        private_key=private_key,
        kid="unknown-key",
    )

    monkeypatch.setattr(
        "ai_it_support_assistant.services.oidc_token_service.get_jwks_client",
        lambda jwks_url: FakeUnknownKeyClient(),
    )

    with pytest.raises(
        OIDCAuthenticationError,
    ):
        decode_oidc_access_token(
            token=token,
            issuer="https://idp.example.com",
            audience="ai-it-support-api",
            jwks_url="https://idp.example.com/jwks",
            algorithms=["RS256"],
        )


def test_decode_oidc_access_token_rejects_unconfigured_algorithm(
    monkeypatch,
) -> None:
    hmac_secret = "test-secret-key-that-is-at-least-32-bytes-long"

    token = jwt.encode(
        {
            "sub": "user-123",
            "iss": "https://idp.example.com",
            "aud": "ai-it-support-api",
            "exp": (
                datetime.now(
                    UTC,
                )
                + timedelta(minutes=5)
            ),
        },
        hmac_secret,
        algorithm="HS256",
        headers={
            "kid": "test-key",
        },
    )

    class FakeClient:
        def get_signing_key_from_jwt(
            self,
            token,
        ):
            return FakeSigningKey(
                hmac_secret,
            )

    monkeypatch.setattr(
        "ai_it_support_assistant.services.oidc_token_service.get_jwks_client",
        lambda jwks_url: FakeClient(),
    )

    with pytest.raises(
        OIDCAuthenticationError,
    ):
        decode_oidc_access_token(
            token=token,
            issuer="https://idp.example.com",
            audience="ai-it-support-api",
            jwks_url="https://idp.example.com/jwks",
            algorithms=["RS256"],
        )
