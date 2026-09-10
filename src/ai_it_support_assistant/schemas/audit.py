from pydantic import BaseModel, ConfigDict, Field


class AuditEvent(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    event_id: str
    event_type: str
    actor: str

    action_type: str | None = None
    approval_id: str | None = None
    resource_id: str | None = None

    details: dict[str, str] = Field(
        default_factory=dict,
    )
