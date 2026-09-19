"""Add continuous_care_available to nurses

Revision ID: 8d52108d045e
Revises: f1c2d3e4a5b6
Create Date: 2026-07-11

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "8d52108d045e"
down_revision: Union[str, Sequence[str], None] = "f1c2d3e4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "nurses",
        sa.Column(
            "continuous_care_available",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.alter_column("nurses", "continuous_care_available", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("nurses", "continuous_care_available")
