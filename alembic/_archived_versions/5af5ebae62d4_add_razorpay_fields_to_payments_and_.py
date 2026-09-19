"""add razorpay fields to payments and create webhook_events table

Revision ID: 5af5ebae62d4
Revises: 1479aa98a363
Create Date: 2026-07-29 19:55:05.222124

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5af5ebae62d4'
down_revision: Union[str, Sequence[str], None] = '1479aa98a363'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # payments: add Razorpay-related columns
    # ------------------------------------------------------------------
    op.add_column("payments", sa.Column("gateway_order_id", sa.String(length=255), nullable=True))
    op.create_unique_constraint(
        "uq_payments_gateway_order_id", "payments", ["gateway_order_id"]
    )
    op.add_column("payments", sa.Column("failure_reason", sa.String(length=255), nullable=True))
    op.add_column("payments", sa.Column("refund_id", sa.String(length=255), nullable=True))
    op.add_column("payments", sa.Column("refunded_amount", sa.Numeric(10, 2), nullable=True))

    # created_at / updated_at: add nullable first, backfill from payment_date
    # (if it still exists), then enforce NOT NULL.
    op.add_column("payments", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("payments", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    # Backfill: use existing payment_date if present, else now().
    # Adjust/remove this line if payment_date was already dropped in an
    # earlier migration.
    op.execute("UPDATE payments SET created_at = COALESCE(payment_date, now())")
    op.execute("UPDATE payments SET updated_at = COALESCE(payment_date, now())")

    op.alter_column("payments", "created_at", nullable=False)
    op.alter_column("payments", "updated_at", nullable=False)

    # Drop payment_date only if it still exists on this branch.
    op.drop_column("payments", "payment_date")

    # ------------------------------------------------------------------
    # webhook_events: new table
    # ------------------------------------------------------------------
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


def downgrade() -> None:
    # ------------------------------------------------------------------
    # webhook_events: drop table
    # ------------------------------------------------------------------
    op.drop_constraint("uq_webhook_events_event_id", "webhook_events", type_="unique")
    op.drop_table("webhook_events")

    # ------------------------------------------------------------------
    # payments: revert
    # ------------------------------------------------------------------
    op.add_column("payments", sa.Column("payment_date", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE payments SET payment_date = created_at")
    op.alter_column("payments", "payment_date", nullable=False)

    op.drop_column("payments", "updated_at")
    op.drop_column("payments", "created_at")
    op.drop_column("payments", "refunded_amount")
    op.drop_column("payments", "refund_id")
    op.drop_column("payments", "failure_reason")

    op.drop_constraint("uq_payments_gateway_order_id", "payments", type_="unique")
    op.drop_column("payments", "gateway_order_id")