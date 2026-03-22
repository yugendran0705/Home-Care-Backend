from config.redis import get_redis_connection

def set_cache(key, value, ex=None):
    """
    Set a value in the cache.
    """
    redis_conn = get_redis_connection()
    redis_conn.set(key, value, ex)


def get_cache(key):
    """
    Get a value from the cache.
    """
    redis_conn = get_redis_connection()
    return redis_conn.get(key)


def delete_cache(key):
    """
    Delete a value from the cache.
    """
    redis_conn = get_redis_connection()
    redis_conn.delete(key)
