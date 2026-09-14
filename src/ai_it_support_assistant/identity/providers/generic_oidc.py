from ai_it_support_assistant.schemas.identity import ExternalIdentity


class OIDCClaimsMappingError(Exception):
    pass


def normalize_string_list(
    value: object,
) -> list[str]:
    if isinstance(value, str):
        return [item for item in value.split() if item]

    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, str)]

    return []


class OIDCClaimsMapper:
    def map_claims(
        self,
        claims: dict[str, object],
    ) -> ExternalIdentity:
        subject = claims.get("sub")
        issuer = claims.get("iss")

        if not isinstance(subject, str) or not subject:
            raise OIDCClaimsMappingError(
                "OIDC subject claim is missing or invalid.",
            )

        if not isinstance(issuer, str) or not issuer:
            raise OIDCClaimsMappingError(
                "OIDC issuer claim is missing or invalid.",
            )

        tenant_id = claims.get("tid")
        email = claims.get("email")
        preferred_username = claims.get(
            "preferred_username",
        )

        return ExternalIdentity(
            subject=subject,
            issuer=issuer,
            tenant_id=(tenant_id if isinstance(tenant_id, str) else None),
            email=(email if isinstance(email, str) else None),
            display_name=(
                preferred_username
                if isinstance(
                    preferred_username,
                    str,
                )
                else None
            ),
            groups=normalize_string_list(
                claims.get("groups"),
            ),
            scopes=normalize_string_list(
                claims.get(
                    "scp",
                    claims.get("scope"),
                ),
            ),
            provider_roles=normalize_string_list(
                claims.get("roles"),
            ),
        )
