from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from ai_it_support_assistant.schemas.incident import (
    IncidentCreateRequest,
)
from ai_it_support_assistant.schemas.kubernetes import (
    DeploymentRestartActionPayload,
)

ActionState = Literal[
    "pending",
    "approved",
    "executing",
    "succeeded",
    "failed",
    "rejected",
]

ActionType = Literal[
    "create_incident",
    "restart_deployment",
]


class PendingAction(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    approval_id: str

    action: ActionType

    requested_by: str

    payload_json: str

    state: ActionState = "pending"

    resource_id: str | None = None

    execution_token: str | None = None

    result_json: str | None = None

    failure_reason: str | None = None

    version: int = 1

    execution_started_at: datetime | None = None

    completed_at: datetime | None = None


class ApprovalExecuteRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    approval_id: str

    approve: bool


class ApprovalStatusResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    approval_id: str

    action: ActionType

    state: ActionState

    resource_id: str | None = None

    execution_token: str | None = None

    failure_reason: str | None = None

    result: dict[str, object] | None = None


class IncidentActionPayload(IncidentCreateRequest):
    pass


class RestartActionPayload(DeploymentRestartActionPayload):
    pass
