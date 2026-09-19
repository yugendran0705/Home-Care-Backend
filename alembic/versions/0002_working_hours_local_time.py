"""working hours: store local wall-clock time without offset

Revision ID: 0002_working_hours_local_time
Revises: 0001_baseline
Create Date: 2026-09-19 20:10:00

working_hours.start_time/end_time were `time with time zone`, but the app
treats them as IST wall-clock times (utils/scheduling.APP_TZ). Postgres
converted each stored offset before comparing, so a slot saved as
08:52+00:00 actually behaved as 14:22 IST.

Each value is converted to the IST wall-clock time it was effectively
behaving as, so no nurse's real availability changes - rows already stored
as +05:30 keep their value, UTC rows move to their IST equivalent.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0002_working_hours_local_time"
down_revision: Union[str, Sequence[str], None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE working_hours
            ALTER COLUMN start_time TYPE time without time zone
                USING (start_time AT TIME ZONE 'Asia/Kolkata')::time,
            ALTER COLUMN end_time TYPE time without time zone
                USING (end_time AT TIME ZONE 'Asia/Kolkata')::time
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE working_hours
            ALTER COLUMN start_time TYPE time with time zone
                USING (start_time::text || '+05:30')::timetz,
            ALTER COLUMN end_time TYPE time with time zone
                USING (end_time::text || '+05:30')::timetz
        """
    )
