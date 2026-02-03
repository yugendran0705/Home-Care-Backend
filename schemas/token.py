# /schemas/token.py

from pydantic import BaseModel

class Token(BaseModel):
    """
    Pydantic schema for the API response when a user logs in.
    """
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshTokenRequest(BaseModel):
    """Schema for refresh token requests."""
    refresh_token: str

    class Config:
        from_attributes = True