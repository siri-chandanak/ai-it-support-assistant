import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

KUBERNETES_NAME_PATTERN = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")


def validate_kubernetes_name(value: str) -> str:
    if not KUBERNETES_NAME_PATTERN.fullmatch(value):
        raise ValueError("Invalid Kubernetes resource name.")

    return value


class DeploymentState(BaseModel):
    resource_type: Literal["deployment"] = "deployment"
    name: str
    namespace: str

    desired_replicas: int
    ready_replicas: int
    available_replicas: int
    updated_replicas: int


class PodState(BaseModel):
    resource_type: Literal["pod"] = "pod"
    name: str
    namespace: str

    phase: str
    ready: bool
    restart_count: int


class DeploymentRestartRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    name: str = Field(
        min_length=1,
        max_length=253,
    )

    namespace: str = Field(
        min_length=1,
        max_length=63,
    )

    @field_validator("name", "namespace")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return validate_kubernetes_name(value)


class DeploymentRestartActionPayload(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    name: str = Field(
        min_length=1,
        max_length=253,
    )

    namespace: str = Field(
        min_length=1,
        max_length=63,
    )

    evidence_desired_replicas: int = Field(ge=0)

    evidence_ready_replicas: int = Field(ge=0)

    evidence_available_replicas: int = Field(ge=0)

    warnings: list[str] = Field(default_factory=list)

    @field_validator(
        "name",
        "namespace",
    )
    @classmethod
    def validate_names(
        cls,
        value: str,
    ) -> str:
        return validate_kubernetes_name(value)
