"""add audit and incident idempotency

Revision ID: 47be8b310dba
Revises: 826128ede34d
Create Date: 2026-09-09 20:38:06.959136

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "47be8b310dba"
down_revision: str | Sequence[str] | None = "826128ede34d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "audit_events",
        sa.Column(
            "event_id",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "event_type",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "actor",
            sa.String(length=120),
            nullable=False,
        ),
        sa.Column(
            "action_type",
            sa.String(length=50),
            nullable=True,
        ),
        sa.Column(
            "approval_id",
            sa.String(length=32),
            nullable=True,
        ),
        sa.Column(
            "resource_id",
            sa.String(length=32),
            nullable=True,
        ),
        sa.Column(
            "details_json",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )

    # 1. Add idempotency_key as nullable first
    op.add_column(
        "incidents",
        sa.Column(
            "idempotency_key",
            sa.String(length=128),
            nullable=True,
        ),
    )

    # 2. Give existing incidents a safe legacy key
    op.execute(
        """
        UPDATE incidents
        SET idempotency_key =
            'legacy:' || incident_id
        WHERE idempotency_key IS NULL
        """
    )

    # 3. Now make it NOT NULL
    op.alter_column(
        "incidents",
        "idempotency_key",
        existing_type=sa.String(length=128),
        nullable=False,
    )

    # 4. Add uniqueness
    op.create_unique_constraint(
        "uq_incidents_idempotency_key",
        "incidents",
        ["idempotency_key"],
    )

    # 5. Step 19 pending-action fields
    op.add_column(
        "pending_incident_actions",
        sa.Column(
            "incident_id",
            sa.String(length=32),
            nullable=True,
        ),
    )

    op.add_column(
        "pending_incident_actions",
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "pending_incident_actions",
        sa.Column(
            "executed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column(
        "pending_incident_actions",
        "executed_at",
    )

    op.drop_column(
        "pending_incident_actions",
        "approved_at",
    )

    op.drop_column(
        "pending_incident_actions",
        "incident_id",
    )

    op.drop_constraint(
        "uq_incidents_idempotency_key",
        "incidents",
        type_="unique",
    )

    op.drop_column(
        "incidents",
        "idempotency_key",
    )

    op.drop_table("audit_events")
