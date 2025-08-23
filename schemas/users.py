# /schemas/user.py

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr

class UserResponse(BaseModel):
    """Schema for safely exposing user data in API responses."""
    id: uuid.UUID
    email: EmailStr
    user_type: str
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    """Schema for user login data."""
    email: EmailStr
    password: str

class UserCreate(BaseModel):
    """Schema for creating a new user."""
    email: EmailStr
    password: str
    user_type: str

class RefreshTokenRequest(BaseModel):
    """Schema for refresh token requests."""
    refresh_token: str