# /config/env.py
"""
Single place for reading configuration from the environment (.env locally,
real environment variables in production). Secrets never live in code.
"""
import os

from dotenv import load_dotenv

load_dotenv()


def require_env(name: str) -> str:
    """Returns a required setting, failing fast with a clear message at startup
    rather than surfacing later as an obscure auth/DB error."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {name}. "
            "Set it in .env (see .env.example) or the deployment environment."
        )
    return value


def int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value not in (None, "") else default
