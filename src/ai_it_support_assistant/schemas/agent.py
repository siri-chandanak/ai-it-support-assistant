from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AgentAction = Literal["rag", "live_status", "kubernetes_state"]

KubernetesResourceType = Literal[
    "deployment",
    "pod",
]


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)


class AgentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: AgentAction

    service_name: str | None

    kubernetes_resource_type: KubernetesResourceType | None
    kubernetes_resource_name: str | None
    kubernetes_namespace: str | None

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
