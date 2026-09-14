from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ai_it_support_assistant.db.base import Base


class ResourcePermissionModel(Base):
    __tablename__ = "resource_permissions"

    permission_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    username: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    permission: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    resource_value: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "username",
            "permission",
            "resource_type",
            "resource_value",
            name="uq_resource_permission",
        ),
    )
