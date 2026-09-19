"""backfill: mark Daily_Shift parents Completed once all shifts are closed

Revision ID: 0003_backfill_completed_parents
Revises: 0002_working_hours_local_time
Create Date: 2026-09-19 20:15:00

BookingService.complete_booking now rolls a Daily_Shift parent up to
Completed when its last open shift is completed. Parents whose shifts were
all completed before that existed are still stuck on Confirmed; this brings
them in line using the same rule (every shift Completed/Cancelled/Rejected,
at least one actually Completed).
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0003_backfill_completed_parents"
down_revision: Union[str, Sequence[str], None] = "0002_working_hours_local_time"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE bookings AS parent
        SET booking_status = 'Completed'
        WHERE parent.is_parent_booking
          AND parent.booking_status = 'Confirmed'
          AND EXISTS (
              SELECT 1 FROM bookings c
              WHERE c.parent_booking_id = parent.booking_id
                AND c.booking_status = 'Completed'
          )
          AND NOT EXISTS (
              SELECT 1 FROM bookings c
              WHERE c.parent_booking_id = parent.booking_id
                AND c.booking_status NOT IN ('Completed', 'Cancelled', 'Rejected')
          )
        """
    )


def downgrade() -> None:
    # Data-only fix; the previous state (a finished booking stuck on
    # Confirmed) was the bug, so there's nothing meaningful to restore.
    pass
