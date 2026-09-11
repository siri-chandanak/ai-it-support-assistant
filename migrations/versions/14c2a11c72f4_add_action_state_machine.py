"""add action state machine

Revision ID: 14c2a11c72f4
Revises: 47be8b310dba
Create Date: 2026-09-10 06:49:41.381353

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "14c2a11c72f4"
down_revision: str | Sequence[str] | None = "47be8b310dba"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "pending_incident_actions",
        sa.Column(
            "action",
            sa.String(length=50),
            nullable=False,
            server_default="create_incident",
        ),
    )

    op.add_column(
        "pending_incident_actions",
        sa.Column(
            "state",
            sa.String(length=20),
            nullable=True,
        ),
    )

    op.add_column(
        "pending_incident_actions",
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )

    op.add_column(
        "pending_incident_actions",
        sa.Column(
            "execution_started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "pending_incident_actions",
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "pending_incident_actions",
        sa.Column(
            "failure_reason",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.execute(
        """
        UPDATE pending_incident_actions
        SET state =
            CASE
                WHEN executed = TRUE THEN 'succeeded'
                WHEN approved = TRUE THEN 'approved'
                ELSE 'pending'
            END
        """
    )

    op.execute(
        """
        UPDATE pending_incident_actions
        SET completed_at = executed_at
        WHERE executed = TRUE
        """
    )

    op.alter_column(
        "pending_incident_actions",
        "state",
        existing_type=sa.String(length=20),
        nullable=False,
        server_default="pending",
    )

    op.create_index(
        "ix_pending_incident_actions_state",
        "pending_incident_actions",
        ["state"],
        unique=False,
    )

    op.drop_column(
        "pending_incident_actions",
        "approved",
    )

    op.drop_column(
        "pending_incident_actions",
        "executed",
    )

    op.drop_column(
        "pending_incident_actions",
        "executed_at",
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.add_column(
        "pending_incident_actions",
        sa.Column(
            "approved",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.add_column(
        "pending_incident_actions",
        sa.Column(
            "executed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
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

    op.execute(
        """
        UPDATE pending_incident_actions
        SET
            approved =
                CASE
                    WHEN state IN (
                        'approved',
                        'executing',
                        'succeeded',
                        'failed'
                    )
                    THEN TRUE
                    ELSE FALSE
                END,
            executed =
                CASE
                    WHEN state = 'succeeded'
                    THEN TRUE
                    ELSE FALSE
                END,
            executed_at =
                CASE
                    WHEN state = 'succeeded'
                    THEN completed_at
                    ELSE NULL
                END
        """
    )

    op.drop_index(
        "ix_pending_incident_actions_state",
        table_name="pending_incident_actions",
    )

    op.drop_column(
        "pending_incident_actions",
        "failure_reason",
    )

    op.drop_column(
        "pending_incident_actions",
        "completed_at",
    )

    op.drop_column(
        "pending_incident_actions",
        "execution_started_at",
    )

    op.drop_column(
        "pending_incident_actions",
        "version",
    )

    op.drop_column(
        "pending_incident_actions",
        "state",
    )

    op.drop_column(
        "pending_incident_actions",
        "action",
    )
