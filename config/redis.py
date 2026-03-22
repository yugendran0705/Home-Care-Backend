import redis
import os
from dotenv import load_dotenv

load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Module-level singleton Redis client (connection pool)
_redis_client = None


def get_redis_connection():
    """
    Returns a singleton Redis connection pool.
    Reuses the same connection pool across all calls to avoid connection overhead.
    Note: Connection exceptions are handled by the calling code (utils/redis.py).
    """
    global _redis_client
    
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=REDIS_HOST, 
            port=REDIS_PORT,
            socket_connect_timeout=2,  # 2 second connection timeout
            socket_timeout=2,           # 2 second operation timeout
            decode_responses=False,    # Binary mode for JSON bytes storage
            max_connections=50         # Connection pool size
        )
    
    return _redis_client
