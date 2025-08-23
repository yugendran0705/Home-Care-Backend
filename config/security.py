# /config/security.py

from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import JWTError, jwt
import os
from dotenv import load_dotenv

load_dotenv()
secret_key = os.getenv("SECRET_KEY")
algorithm = os.getenv("ALGORITHM")
access_token_expire_minutes = os.getenv("ACCESS_TOKEN_EXPIRE_DAYS")
refresh_token_expire_dates = os.getenv("REFRESH_TOKEN_EXPIRE_DAYS")

bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated = 'auto')

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(days=access_token_expire_minutes or 1)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode,  secret_key, algorithm=algorithm or 'HS256')
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(days=int(refresh_token_expire_dates) or 30)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm or 'HS256')
    return encoded_jwt

def verify_token(token: str):
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm or 'HS256'])
        return payload
    except JWTError:
        return None