from typing import Literal

from pydantic import BaseModel

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


class ApprovalExecuteRequest(BaseModel):
    approval_id: str
    approve: bool
