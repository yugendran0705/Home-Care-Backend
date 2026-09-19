"""Add completion OTP fields to bookings

Revision ID: a3f7c1d94b02
Revises: 1e2a2a7454be
Create Date: 2026-09-13

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a3f7c1d94b02"
down_revision: Union[str, Sequence[str], None] = "1e2a2a7454be"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("bookings", sa.Column("completion_otp", sa.String(length=6), nullable=True))
    op.add_column(
        "bookings",
        sa.Column(
            "completion_otp_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.alter_column("bookings", "completion_otp_attempts", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("bookings", "completion_otp_attempts")
    op.drop_column("bookings", "completion_otp")
