from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

IncidentSeverity = Literal[
    "low",
    "medium",
    "high",
    "critical",
]


class IncidentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(
        min_length=5,
        max_length=120,
    )

    description: str = Field(
        min_length=10,
        max_length=2000,
    )

    severity: IncidentSeverity

    service_name: str | None = None


class IncidentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    incident_id: str

    title: str
    description: str
    severity: IncidentSeverity
    service_name: str | None

    created_by: str

    status: Literal["open"] = "open"
    created_at: datetime


class IncidentExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident: IncidentRecord
    created: bool
