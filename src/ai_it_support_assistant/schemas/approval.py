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
    action: str
    requested_by: str
    requested_roles_json: str = "[]"

    payload_json: str

    state: str
    version: int

    resource_id: str | None = None
    execution_token: str | None = None
    failure_reason: str | None = None

    created_at: datetime | None = None
    approved_at: datetime | None = None
    execution_started_at: datetime | None = None
    completed_at: datetime | None = None

    worker_id: str | None = None
    last_heartbeat_at: datetime | None = None

    result_json: str | None = None

    origin_trace_id: str | None = None
    origin_request_id: str | None = None


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
    created_at: datetime | None = None
    approved_at: datetime | None = None
    execution_started_at: datetime | None = None
    completed_at: datetime | None = None


class IncidentActionPayload(IncidentCreateRequest):
    pass


class RestartActionPayload(DeploymentRestartActionPayload):
    pass
