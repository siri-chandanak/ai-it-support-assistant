import pytest

from ai_it_support_assistant.identity.providers.generic_oidc import (
    OIDCClaimsMapper,
    OIDCClaimsMappingError,
)


def test_oidc_claims_mapper_maps_identity() -> None:
    mapper = OIDCClaimsMapper()

    identity = mapper.map_claims(
        {
            "sub": "user-123",
            "iss": "https://idp.example.com",
            "tid": "tenant-1",
            "email": "alice@example.com",
            "preferred_username": "alice",
            "groups": ["support-team"],
            "scp": "knowledge.read kubernetes.read",
            "roles": ["SupportEngineer"],
        }
    )

    assert identity.subject == "user-123"
    assert identity.issuer == "https://idp.example.com"
    assert identity.tenant_id == "tenant-1"
    assert identity.email == "alice@example.com"
    assert identity.display_name == "alice"

    assert identity.groups == [
        "support-team",
    ]

    assert identity.scopes == [
        "knowledge.read",
        "kubernetes.read",
    ]

    assert identity.provider_roles == [
        "SupportEngineer",
    ]


def test_oidc_claims_mapper_rejects_missing_subject() -> None:
    mapper = OIDCClaimsMapper()

    with pytest.raises(OIDCClaimsMappingError):
        mapper.map_claims(
            {
                "iss": "https://idp.example.com",
            }
        )


def test_oidc_claims_mapper_rejects_missing_issuer() -> None:
    mapper = OIDCClaimsMapper()

    with pytest.raises(OIDCClaimsMappingError):
        mapper.map_claims(
            {
                "sub": "user-123",
            }
        )
