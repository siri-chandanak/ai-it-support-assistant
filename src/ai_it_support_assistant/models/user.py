from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from ai_it_support_assistant.db.base import Base


class UserModel(Base):
    __tablename__ = "users"

    __table_args__ = (
        UniqueConstraint(
            "external_issuer",
            "external_subject",
            name="uq_users_external_identity",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    username: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    hashed_password: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )

    roles: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    disabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    external_subject: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    external_issuer: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    tenant_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
