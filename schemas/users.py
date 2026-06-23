# /schemas/user.py

import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from .address import Address as AddressResponse

class UserResponse(BaseModel):
    """Schema for safely exposing user data in API responses."""
    id: uuid.UUID
    email: EmailStr
    user_type: str
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None
    addresses: List[AddressResponse] = Field(default_factory=list)

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

class UserUpdate(BaseModel):
    """Schema for updating user information."""
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    user_type: Optional[str] = None
    is_active: Optional[bool] = None
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True