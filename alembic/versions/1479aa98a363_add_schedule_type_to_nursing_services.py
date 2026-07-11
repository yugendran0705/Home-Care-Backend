"""Add schedule_type to nursing_services, backfilled from is_continuous

Revision ID: 1479aa98a363
Revises: 8d52108d045e
Create Date: 2026-07-11

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "1479aa98a363"
down_revision: Union[str, Sequence[str], None] = "8d52108d045e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "nursing_services",
        sa.Column("schedule_type", sa.String(length=20), nullable=True),
    )

    op.execute(
        """
        UPDATE nursing_services
        SET schedule_type = CASE
            WHEN is_continuous IS TRUE THEN 'Continuous'
            ELSE 'Daily_Shift'
        END
        """
    )

    op.alter_column("nursing_services", "schedule_type", nullable=False)
    op.execute("ALTER TABLE nursing_services DROP COLUMN IF EXISTS is_continuous")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "nursing_services",
        sa.Column("is_continuous", sa.Boolean(), nullable=True),
    )
    op.execute(
        """
        UPDATE nursing_services
        SET is_continuous = (schedule_type = 'Continuous')
        """
    )
    op.drop_column("nursing_services", "schedule_type")
