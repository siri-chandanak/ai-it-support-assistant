from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ai_it_support_assistant.db.base import Base


class IncidentModel(Base):
    __tablename__ = "incidents"

    incident_id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    service_name: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    created_by: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="open",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class PendingActionModel(Base):
    __tablename__ = "pending_actions"

    approval_id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
    )

    requested_by: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="create_incident",
    )

    payload_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    state: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )

    version: Mapped[int] = mapped_column(
        nullable=False,
        default=1,
    )

    resource_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    execution_token: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    worker_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    requested_roles_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
    )

    result_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    execution_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    failure_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    incident_title: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    incident_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    incident_severity: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    service_name: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    incident_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
