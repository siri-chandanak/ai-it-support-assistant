"""add incident approval tables

Revision ID: 826128ede34d
Revises: 0d3486e09c31
Create Date: 2026-09-09 18:44:28.228458

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "826128ede34d"
down_revision: str | Sequence[str] | None = "0d3486e09c31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
