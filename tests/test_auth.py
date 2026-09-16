from uuid import uuid4

import pytest

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.services.auth_service import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from ai_it_support_assistant.services.document_access_validation_service import (
    AuthorizationConfigurationError,
    validate_allowed_roles,
)
from ai_it_support_assistant.services.retrieval_service import (
    build_authorization_filter,
    build_retrieval_cache_key,
)


def test_password_hash_verification() -> None:
    hashed = hash_password("example-password")

    assert hashed != "example-password"

    assert verify_password(
        "example-password",
        hashed,
    )

    assert not verify_password(
        "wrong-password",
        hashed,
    )


def test_access_token_round_trip() -> None:
    user_id = uuid4()

    user = User(
        user_id=user_id,
        username="alice",
        roles=["it_support"],
    )
    TEST_SECRET = "test-secret-key-that-is-longer-than-32-bytes"
    token = create_access_token(
        user=user,
        secret_key=TEST_SECRET,
        algorithm="HS256",
        expire_minutes=30,
    )

    token_data = decode_access_token(
        token=token,
        secret_key=TEST_SECRET,
        algorithm="HS256",
    )

    assert token_data.user_id == user_id


def test_valid_document_roles() -> None:
    roles = validate_allowed_roles(
        [
            "admin",
            "it_support",
            "admin",
        ]
    )

    assert roles == [
        "admin",
        "it_support",
    ]


def test_invalid_document_role() -> None:
    with pytest.raises(AuthorizationConfigurationError):
        validate_allowed_roles(["super-secret-role"])


def test_authorization_filter_uses_user_roles() -> None:
    authorization_filter = build_authorization_filter(
        [
            "reader",
            "it_support",
        ]
    )

    assert authorization_filter is not None


def test_retrieval_cache_key_includes_roles() -> None:
    admin_key = build_retrieval_cache_key(
        query="VPN",
        model_name="model",
        collection_name="docs",
        top_k=3,
        user_roles=["admin"],
    )

    reader_key = build_retrieval_cache_key(
        query="VPN",
        model_name="model",
        collection_name="docs",
        top_k=3,
        user_roles=["reader"],
    )

    assert admin_key != reader_key


def test_token_endpoint_disabled_in_oidc_mode(
    client,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "AUTH_MODE",
        "oidc",
    )

    get_settings.cache_clear()

    try:
        response = client.post(
            "/api/v1/auth/token",
            data={
                "username": "anything",
                "password": "anything",
            },
        )

        assert response.status_code == 404

    finally:
        get_settings.cache_clear()
