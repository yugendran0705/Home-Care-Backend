import redis
import os
from dotenv import load_dotenv

load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")


def get_redis_connection():
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
