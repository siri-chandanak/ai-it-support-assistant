from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ai_it_support_assistant.schemas.incident import (
    IncidentCreateRequest,
)

AgentAction = Literal["rag", "live_status", "kubernetes_state", "create_incident"]

KubernetesResourceType = Literal[
    "deployment",
    "pod",
]

IncidentSeverity = Literal[
    "low",
    "medium",
    "high",
    "critical",
]


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)


class AgentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: AgentAction

    service_name: str | None = None

    kubernetes_resource_type: KubernetesResourceType | None = None
    kubernetes_resource_name: str | None = None
    kubernetes_namespace: str | None = None

    incident_title: str | None = None
    incident_description: str | None = None
    incident_severity: IncidentSeverity | None = None

    reasoning_summary: str


class ToolExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    success: bool
    content: str


class AgentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    action: AgentAction
    answer: str

    approval_required: bool = False
    approval_id: str | None = None

    proposed_incident: IncidentCreateRequest | None = None

    incident_id: str | None = None


class AgentRoutingOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: AgentAction

    service_name: str | None

    kubernetes_resource_type: KubernetesResourceType | None
    kubernetes_resource_name: str | None
    kubernetes_namespace: str | None

    incident_title: str | None
    incident_description: str | None
    incident_severity: IncidentSeverity | None

    reasoning_summary: str
