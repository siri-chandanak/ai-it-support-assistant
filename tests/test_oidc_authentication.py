from unittest.mock import Mock

import pytest

from ai_it_support_assistant.core.config import Settings
from ai_it_support_assistant.schemas.identity import ExternalIdentity
from ai_it_support_assistant.services import (
    oidc_authentication_service,
)
from ai_it_support_assistant.services.oidc_authentication_service import (
    OIDCAuthorizationError,
)


def test_authenticate_oidc_user_returns_internal_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        auth_mode="oidc",
        oidc_issuer="https://idp.example.com",
        oidc_audience="ai-it-support-api",
        oidc_jwks_url="https://idp.example.com/jwks",
        oidc_algorithms="RS256",
        oidc_required_scope="ai-support.access",
    )

    claims = {
        "sub": "external-user-123",
        "iss": "https://idp.example.com",
        "scp": "ai-support.access",
    }

    monkeypatch.setattr(
        oidc_authentication_service,
        "decode_oidc_access_token",
        lambda **kwargs: claims,
    )

    identity = ExternalIdentity(
        subject="external-user-123",
        issuer="https://idp.example.com",
        scopes=["ai-support.access"],
    )

    mapper = Mock()
    mapper.map_claims.return_value = identity

    monkeypatch.setattr(
        oidc_authentication_service,
        "OIDCClaimsMapper",
        lambda: mapper,
    )

    expected_user = Mock()

    resolve_mock = Mock(
        return_value=expected_user,
    )

    monkeypatch.setattr(
        oidc_authentication_service,
        "resolve_external_user",
        resolve_mock,
    )

    session = Mock()

    result = oidc_authentication_service.authenticate_oidc_user(
        token="external-token",
        settings=settings,
        session=session,
    )

    assert result is expected_user

    mapper.map_claims.assert_called_once_with(
        claims,
    )

    resolve_mock.assert_called_once_with(
        identity=identity,
        session=session,
    )


def test_authenticate_oidc_user_rejects_missing_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        auth_mode="oidc",
        oidc_issuer="https://idp.example.com",
        oidc_audience="ai-it-support-api",
        oidc_jwks_url="https://idp.example.com/jwks",
        oidc_algorithms="RS256",
        oidc_required_scope="ai-support.access",
    )

    monkeypatch.setattr(
        oidc_authentication_service,
        "decode_oidc_access_token",
        lambda **kwargs: {
            "sub": "external-user-123",
            "iss": "https://idp.example.com",
        },
    )

    identity = ExternalIdentity(
        subject="external-user-123",
        issuer="https://idp.example.com",
        scopes=["something-else"],
    )

    mapper = Mock()
    mapper.map_claims.return_value = identity

    monkeypatch.setattr(
        oidc_authentication_service,
        "OIDCClaimsMapper",
        lambda: mapper,
    )

    with pytest.raises(
        OIDCAuthorizationError,
    ):
        oidc_authentication_service.authenticate_oidc_user(
            token="external-token",
            settings=settings,
            session=Mock(),
        )


def test_authenticate_oidc_user_rejects_unknown_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        auth_mode="oidc",
        oidc_issuer="https://idp.example.com",
        oidc_audience="ai-it-support-api",
        oidc_jwks_url="https://idp.example.com/jwks",
        oidc_algorithms="RS256",
        oidc_required_scope="ai-support.access",
    )

    monkeypatch.setattr(
        oidc_authentication_service,
        "decode_oidc_access_token",
        lambda **kwargs: {
            "sub": "unknown-user",
            "iss": "https://idp.example.com",
            "scp": "ai-support.access",
        },
    )

    identity = ExternalIdentity(
        subject="unknown-user",
        issuer="https://idp.example.com",
        scopes=["ai-support.access"],
    )

    mapper = Mock()
    mapper.map_claims.return_value = identity

    monkeypatch.setattr(
        oidc_authentication_service,
        "OIDCClaimsMapper",
        lambda: mapper,
    )

    from ai_it_support_assistant.services.identity_service import (
        ExternalUserNotProvisionedError,
    )

    def reject_user(**kwargs):
        raise ExternalUserNotProvisionedError(
            "not provisioned",
        )

    monkeypatch.setattr(
        oidc_authentication_service,
        "resolve_external_user",
        reject_user,
    )

    with pytest.raises(
        OIDCAuthorizationError,
    ):
        oidc_authentication_service.authenticate_oidc_user(
            token="external-token",
            settings=settings,
            session=Mock(),
        )
