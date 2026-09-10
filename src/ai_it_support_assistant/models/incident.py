from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String, Text
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


class PendingIncidentActionModel(Base):
    __tablename__ = "pending_incident_actions"

    approval_id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
    )

    requested_by: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    incident_title: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    incident_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    incident_severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    service_name: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    approved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    executed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    incident_id: Mapped[str | None] = mapped_column(
        String(32),
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

    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
