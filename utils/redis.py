import time
from contextlib import contextmanager

from redis.exceptions import LockError

from config.redis import get_redis_connection
import logging

logger = logging.getLogger(__name__)

# Default TTL for patient cache entries (15 minutes)
PATIENT_CACHE_TTL = 900
# Default TTL for service cache entries (60 minutes/1 hour)
SERVICE_CACHE_TTL = 3600
NURSE_CACHE_TTL = 900

# --- Distributed lock config for booking a nurse -----------------------------
# TTL is a SAFETY VALVE only: if the process holding the lock crashes mid-transaction
# the lock auto-expires after this many seconds so future bookings aren't deadlocked.
# It is NOT how long the nurse stays reserved - that is the Pending booking row in
# Postgres. The lock is released the instant the DB transaction commits.
NURSE_LOCK_TTL_SECONDS = 10
# How long a request will wait to acquire the lock before giving up (fail fast).
NURSE_LOCK_BLOCKING_TIMEOUT_SECONDS = 5


class LockAcquisitionError(Exception):
    """Raised when the per-nurse booking lock could not be acquired in time."""


@contextmanager
def nurse_booking_lock(
    nurse_id,
    ttl: int = NURSE_LOCK_TTL_SECONDS,
    blocking_timeout: int = NURSE_LOCK_BLOCKING_TIMEOUT_SECONDS,
):
    """
    A blocking, per-nurse distributed lock (Redis SET NX PX under the hood).

    Serializes the "check availability -> insert pending booking" critical section
    so two concurrent requests for the same nurse cannot both pass the availability
    check before either has committed its row.

    Usage:
        with nurse_booking_lock(nurse_id):
            ...  # re-check availability + insert booking + payment, then commit
    """
    redis_conn = get_redis_connection()
    lock = redis_conn.lock(
        f"nurse_booking_lock:{nurse_id}",
        timeout=ttl,
        blocking=True,
        blocking_timeout=blocking_timeout,
    )
    acquired = lock.acquire()
    if not acquired:
        raise LockAcquisitionError(
            "Could not acquire booking lock for this nurse. Please retry."
        )
    try:
        yield
    finally:
        # If the transaction outran the TTL the lock may already be gone; ignore.
        try:
            lock.release()
        except LockError:
            logger.warning(
                "Booking lock for nurse %s expired before release (TTL too low?).",
                nurse_id,
            )


# --- Delayed-queue (ZSET) for pending-booking expiry -------------------------
# A Redis sorted set acting as a delayed queue: member = booking_id, score = the
# unix timestamp at which the booking should be cancelled if still unpaid. The
# score is an absolute epoch value (time.time()), so it is timezone/DST-agnostic
# by construction. A sweeper worker reads only members whose score has passed
# (ZRANGEBYSCORE), so cost scales with bookings actually due, not the whole table
# (unlike a cron scan). Everything persists until explicitly ZREM'd, so a worker
# restart loses nothing.
BOOKING_EXPIRY_ZSET = "booking:expiry"

# How long an unpaid Pending booking is held before the sweeper cancels it.
BOOKING_EXPIRY_SECONDS = 300  # 5 minutes


def schedule_booking_expiry(booking_id, fire_at_ts: float) -> bool:
    """
    Register a booking's cancellation deadline. `fire_at_ts` is a unix timestamp
    (time.time() + BOOKING_EXPIRY_SECONDS). Returns False if Redis is unavailable.
    """
    try:
        get_redis_connection().zadd(
            BOOKING_EXPIRY_ZSET, {str(booking_id): fire_at_ts}
        )
        return True
    except Exception as e:
        logger.warning(f"Redis schedule_booking_expiry failed for '{booking_id}': {e}")
        return False


# Retry budget for absorbing a momentary Redis blip when scheduling a
# booking's expiry timer, before the caller treats it as a real outage.
SCHEDULE_EXPIRY_MAX_ATTEMPTS = 3
SCHEDULE_EXPIRY_RETRY_DELAY_SECONDS = 0.2


def schedule_booking_expiry_with_retry(
    booking_id,
    fire_at_ts: float,
    max_attempts: int = SCHEDULE_EXPIRY_MAX_ATTEMPTS,
    retry_delay: float = SCHEDULE_EXPIRY_RETRY_DELAY_SECONDS,
) -> bool:
    """
    Like schedule_booking_expiry, but retries a few times on failure before
    giving up. A single dropped connection or momentary network hiccup
    shouldn't be treated the same as a real outage - this absorbs that.
    Returns False only after every attempt has failed.
    """
    for attempt in range(max_attempts):
        if schedule_booking_expiry(booking_id, fire_at_ts):
            return True
        if attempt < max_attempts - 1:
            time.sleep(retry_delay)
    return False


def cancel_booking_expiry(booking_id) -> bool:
    """
    Remove a booking's timer (called once it's Confirmed or Cancelled so the
    sweeper never has to look at it). Harmless if it wasn't scheduled.
    """
    try:
        get_redis_connection().zrem(BOOKING_EXPIRY_ZSET, str(booking_id))
        return True
    except Exception as e:
        logger.warning(f"Redis cancel_booking_expiry failed for '{booking_id}': {e}")
        return False


def get_due_booking_expiries(now_ts: float, limit: int = 100):
    """
    Return up to `limit` booking_ids (as str) whose deadline has passed. Empty
    list when nothing is due or Redis is unavailable.
    """
    try:
        due = get_redis_connection().zrangebyscore(
            BOOKING_EXPIRY_ZSET, 0, now_ts, start=0, num=limit
        )
        return [b.decode() if isinstance(b, bytes) else b for b in due]
    except Exception as e:
        logger.warning(f"Redis get_due_booking_expiries failed: {e}")
        return []


def peek_next_booking_expiry():
    """
    Return the earliest deadline score (float) in the set, or None if empty /
    unavailable. Lets the sweeper sleep exactly until the next deadline instead
    of polling on a fixed tick.
    """
    try:
        res = get_redis_connection().zrange(
            BOOKING_EXPIRY_ZSET, 0, 0, withscores=True
        )
        return res[0][1] if res else None
    except Exception as e:
        logger.warning(f"Redis peek_next_booking_expiry failed: {e}")
        return None


def set_cache(key, value, ex=None):
    """
    Set a value in the cache with optional TTL.
    
    Args:
        key: Cache key
        value: Value to cache (bytes)
        ex: Expiration time in seconds (None for no expiration)
        
    Returns True if successful, False if Redis is unavailable.
    """
    try:
        redis_conn = get_redis_connection()
        redis_conn.set(key, value, ex)
        return True
    except Exception as e:
        logger.warning(f"Redis set_cache failed for key '{key}': {e}")
        return False


def get_cache(key):
    """
    Get a value from the cache.
    Returns None if key not found or Redis is unavailable.
    """
    try:
        redis_conn = get_redis_connection()
        return redis_conn.get(key)
    except Exception as e:
        logger.warning(f"Redis get_cache failed for key '{key}': {e}")
        return None


def delete_cache(key):
    """
    Delete a value from the cache.
    Returns True if successful, False if Redis is unavailable.
    """
    try:
        redis_conn = get_redis_connection()
        redis_conn.delete(key)
        return True
    except Exception as e:
        logger.warning(f"Redis delete_cache failed for key '{key}': {e}")
        return False


