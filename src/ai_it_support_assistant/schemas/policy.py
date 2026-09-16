from typing import Any

from pydantic import BaseModel, Field


class PolicySubject(BaseModel):
    subject_id: str
    username: str

    roles: list[str] = Field(
        default_factory=list,
    )

    permissions: list[str] = Field(
        default_factory=list,
    )

    tenant_id: str | None = None
    disabled: bool = False


class PolicyResource(BaseModel):
    resource_type: str
    resource_id: str | None = None

    attributes: dict[str, Any] = Field(
        default_factory=dict,
    )


class PolicyContext(BaseModel):
    attributes: dict[str, Any] = Field(
        default_factory=dict,
    )


class PolicyRequest(BaseModel):
    subject: PolicySubject
    action: str
    resource: PolicyResource

    context: PolicyContext = Field(
        default_factory=PolicyContext,
    )


class PolicyDecision(BaseModel):
    allowed: bool
    reason_code: str
    reason: str
    policy_id: str

    obligations: list[str] = Field(
        default_factory=list,
    )
