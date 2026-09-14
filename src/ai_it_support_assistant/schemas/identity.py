from pydantic import BaseModel, Field


class ExternalIdentity(BaseModel):
    subject: str
    issuer: str
    tenant_id: str | None = None
    email: str | None = None
    display_name: str | None = None

    groups: list[str] = Field(
        default_factory=list,
    )

    scopes: list[str] = Field(
        default_factory=list,
    )

    provider_roles: list[str] = Field(
        default_factory=list,
    )
