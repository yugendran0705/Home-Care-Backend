# workers/booking_expiry_worker.py
"""
Standalone sweeper process for the booking:expiry Redis ZSET (delayed queue).

Run this as its own long-running process, separate from the FastAPI/uvicorn
process (it blocks in a loop):

    python -m workers.booking_expiry_worker

Design: peek the earliest deadline and sleep exactly until it's due (capped),
instead of polling on a fixed tick - so idle cost is near zero and expiry
latency is sub-second, unlike a cron table-scan. See utils/redis.py for the
ZSET helpers (schedule/cancel/get_due/peek).
"""
import logging
import time
import uuid

from config.database import SessionLocal
from services.bookings import BookingService
from utils.redis import (
    cancel_booking_expiry,
    get_due_booking_expiries,
    peek_next_booking_expiry,
    schedule_booking_expiry,
)

logger = logging.getLogger(__name__)

# Upper bound on how long we ever sleep in one go, so the worker still wakes
# periodically even if Redis was briefly unavailable when we last peeked.
MAX_SLEEP_SECONDS = 30
BATCH_LIMIT = 100
# On an unexpected failure, push the timer into the future rather than dropping
# it (would leak a Pending booking that never expires) or leaving it overdue
# (would spin the loop) - an at-least-once retry with backoff.
RETRY_BACKOFF_SECONDS = 60


def _process_due_bookings(now_ts: float) -> int:
    """
    Pulls whatever is due at `now_ts` and cancels each if it's still Pending.
    Each booking is handled in the SAME transaction pattern as the webhook
    path (row-locked, idempotent) - see BookingService.cancel_if_still_pending.
    """
    due_ids = get_due_booking_expiries(now_ts, limit=BATCH_LIMIT)
    if not due_ids:
        return 0

    db = SessionLocal()
    try:
        service = BookingService(db)
        for raw_id in due_ids:
            try:
                booking_id = uuid.UUID(raw_id)
            except ValueError:
                logger.warning("Dropping malformed booking id from expiry ZSET: %r", raw_id)
                cancel_booking_expiry(raw_id)
                continue
            try:
                service.cancel_if_still_pending(booking_id)
            except Exception:
                logger.exception(
                    "Failed to expire booking %s; retrying in %ss",
                    booking_id,
                    RETRY_BACKOFF_SECONDS,
                )
                schedule_booking_expiry(booking_id, time.time() + RETRY_BACKOFF_SECONDS)
                continue
            cancel_booking_expiry(booking_id)
    finally:
        db.close()

    return len(due_ids)


def run_forever() -> None:
    logger.info("Booking expiry sweeper started.")
    while True:
        next_deadline = peek_next_booking_expiry()

        if next_deadline is None:
            # Nothing scheduled (or Redis briefly unavailable) - idle.
            time.sleep(MAX_SLEEP_SECONDS)
            continue

        wait_seconds = next_deadline - time.time()
        if wait_seconds > 0:
            time.sleep(min(wait_seconds, MAX_SLEEP_SECONDS))
            continue

        processed = _process_due_bookings(time.time())
        if processed == 0:
            # Guards against a tight loop if the score was already claimed by
            # another sweeper instance between peek and process.
            time.sleep(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_forever()
