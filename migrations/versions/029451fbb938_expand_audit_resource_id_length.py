"""expand audit resource id length

Revision ID: 029451fbb938
Revises: 17a2bbefb934
Create Date: 2026-09-24 16:02:53.426985

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "029451fbb938"
down_revision: str | Sequence[str] | None = "17a2bbefb934"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "audit_events",
        "resource_id",
        existing_type=sa.String(length=32),
        type_=sa.String(length=255),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "audit_events",
        "resource_id",
        existing_type=sa.String(length=255),
        type_=sa.String(length=32),
        existing_nullable=True,
    )
