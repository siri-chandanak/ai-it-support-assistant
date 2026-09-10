from typing import Literal

from pydantic import BaseModel, ConfigDict

from ai_it_support_assistant.schemas.incident import (
    IncidentCreateRequest,
)


class PendingIncidentAction(BaseModel):
    approval_id: str

    action: Literal["create_incident"] = "create_incident"

    requested_by: str

    incident: IncidentCreateRequest

    approved: bool = False
    executed: bool = False

    incident_id: str | None = None


class ApprovalExecuteRequest(BaseModel):
    approval_id: str
    approve: bool


class ApprovalStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: str
    action: str
    approved: bool
    executed: bool
    incident_id: str | None = None
