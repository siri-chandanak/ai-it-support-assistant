"""generalize pending actions for kubernetes restart

Revision ID: 7c68ac132c03
Revises: 14c2a11c72f4
Create Date: 2026-09-11 01:01:17.934304

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c68ac132c03"
down_revision: str | Sequence[str] | None = "14c2a11c72f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table(
        "pending_incident_actions",
        "pending_actions",
    )

    op.add_column(
        "pending_actions",
        sa.Column(
            "payload_json",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "pending_actions",
        sa.Column(
            "resource_id",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "pending_actions",
        sa.Column(
            "execution_token",
            sa.String(length=128),
            nullable=True,
        ),
    )

    # Existing rows are create_incident actions.
    # Convert their incident-specific columns into the new
    # generic JSON payload.
    op.execute(
        """
        UPDATE pending_actions
        SET payload_json = json_build_object(
            'title', incident_title,
            'description', incident_description,
            'severity', incident_severity,
            'service_name', service_name
        )::text
        WHERE payload_json IS NULL
        """
    )

    # Existing successful incident actions already have a
    # resource identifier: incident_id.
    op.execute(
        """
        UPDATE pending_actions
        SET resource_id = incident_id
        WHERE incident_id IS NOT NULL
          AND resource_id IS NULL
        """
    )

    op.alter_column(
        "pending_actions",
        "payload_json",
        existing_type=sa.Text(),
        nullable=False,
    )

    # The old incident-specific columns cannot remain NOT NULL,
    # because restart_deployment does not have incident fields.
    op.alter_column(
        "pending_actions",
        "incident_title",
        existing_type=sa.String(length=120),
        nullable=True,
    )

    op.alter_column(
        "pending_actions",
        "incident_description",
        existing_type=sa.Text(),
        nullable=True,
    )

    op.alter_column(
        "pending_actions",
        "incident_severity",
        existing_type=sa.String(length=20),
        nullable=True,
    )


def downgrade() -> None:
    # A downgrade back to the incident-only model is only valid
    # if no non-incident actions exist.
    connection = op.get_bind()

    non_incident_count = connection.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM pending_actions
            WHERE action <> 'create_incident'
            """
        )
    ).scalar_one()

    if non_incident_count > 0:
        raise RuntimeError("Cannot downgrade pending_actions while non-incident actions exist.")

    op.execute(
        """
        UPDATE pending_actions
        SET
            incident_title =
                payload_json::json ->> 'title',
            incident_description =
                payload_json::json ->> 'description',
            incident_severity =
                payload_json::json ->> 'severity',
            service_name =
                payload_json::json ->> 'service_name'
        WHERE action = 'create_incident'
        """
    )

    op.alter_column(
        "pending_actions",
        "incident_title",
        existing_type=sa.String(length=120),
        nullable=False,
    )

    op.alter_column(
        "pending_actions",
        "incident_description",
        existing_type=sa.Text(),
        nullable=False,
    )

    op.alter_column(
        "pending_actions",
        "incident_severity",
        existing_type=sa.String(length=20),
        nullable=False,
    )

    op.drop_column(
        "pending_actions",
        "execution_token",
    )

    op.drop_column(
        "pending_actions",
        "resource_id",
    )

    op.drop_column(
        "pending_actions",
        "payload_json",
    )

    op.rename_table(
        "pending_actions",
        "pending_incident_actions",
    )
