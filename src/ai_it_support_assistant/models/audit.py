from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ai_it_support_assistant.db.base import Base


class AuditEventModel(Base):
    __tablename__ = "audit_events"

    event_id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    actor: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    action_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    approval_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    resource_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    details_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="{}",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
