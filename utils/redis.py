from config.redis import get_redis_connection
import logging

logger = logging.getLogger(__name__)

# Default TTL for patient cache entries (15 minutes)
PATIENT_CACHE_TTL = 900
# Default TTL for service cache entries (60 minutes/1 hour)
SERVICE_CACHE_TTL = 3600
NURSE_CACHE_TTL = 900


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


