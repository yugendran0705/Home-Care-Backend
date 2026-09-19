# /config/security.py

from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
import os

from config.env import int_env, require_env

# Signing key for every JWT: without it tokens would be signed with None.
secret_key = require_env("SECRET_KEY")
algorithm = os.getenv("ALGORITHM") or "HS256"
access_token_expire_minutes = int_env("ACCESS_TOKEN_EXPIRE_MINUTES", 60)
refresh_token_expire_days = int_env("REFRESH_TOKEN_EXPIRE_DAYS", 30)

bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated = 'auto')

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # UTC: jose treats a naive datetime as UTC, so a naive local (IST)
        # time would silently push every expiry 5h30m later.
        expire = datetime.now(timezone.utc) + timedelta(minutes=access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=refresh_token_expire_days)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encoded_jwt

def verify_token(token: str):
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return payload
    except JWTError:
        return None