from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from ai_it_support_assistant.schemas.incident import (
    IncidentCreateRequest,
)

ActionState = Literal[
    "pending",
    "approved",
    "executing",
    "succeeded",
    "failed",
    "rejected",
]


class PendingIncidentAction(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    approval_id: str

    action: Literal["create_incident"] = "create_incident"

    requested_by: str

    incident: IncidentCreateRequest

    state: ActionState = "pending"

    incident_id: str | None = None

    failure_reason: str | None = None

    version: int = 1

    execution_started_at: datetime | None = None
    completed_at: datetime | None = None


class ApprovalExecuteRequest(BaseModel):
    approval_id: str
    approve: bool


class ApprovalStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str
    action: str
    state: ActionState
    incident_id: str | None = None
    failure_reason: str | None = None
