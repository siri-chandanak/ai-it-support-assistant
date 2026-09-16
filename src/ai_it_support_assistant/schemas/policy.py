from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def generate_policy_decision_id() -> str:
    return f"POL-{uuid4().hex[:12].upper()}"


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


class PolicyTraceStep(BaseModel):
    rule_id: str
    outcome: str
    detail: str | None = None


class PolicyDecision(BaseModel):
    decision_id: str = Field(default_factory=generate_policy_decision_id)
    allowed: bool
    reason_code: str
    reason: str
    policy_id: str

    obligations: list[str] = Field(
        default_factory=list,
    )
    trace: list[PolicyTraceStep] = Field(default_factory=list)
