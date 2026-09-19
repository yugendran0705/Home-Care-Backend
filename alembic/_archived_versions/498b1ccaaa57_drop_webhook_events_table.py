"""drop webhook_events table

Revision ID: 498b1ccaaa57
Revises: 5af5ebae62d4
Create Date: 2026-08-07 19:34:57.003039

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '498b1ccaaa57'
down_revision: Union[str, Sequence[str], None] = '5af5ebae62d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("uq_webhook_events_event_id", "webhook_events", type_="unique")
    op.drop_table("webhook_events")


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        "webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="razorpay"),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("processing_error", sa.String(length=500), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_webhook_events_event_id", "webhook_events", ["event_id"])