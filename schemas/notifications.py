# /schemas/notifications.py

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class NotificationBase(BaseModel):
    """
    Base schema for a notification, containing the core fields provided during creation.
    """
    type: str = Field(..., examples=["booking_confirmed", "policy_update"])
    title: str
    body: str
    data: dict = {}
    audience_type: Literal["global", "role", "user"]
    audience_role: Optional[Literal["Patient", "Nurse"]] = None
    target_user_id: Optional[uuid.UUID] = None

    @model_validator(mode='after')
    def audience_fields_match_audience_type(self) -> 'NotificationBase':
        if self.audience_type == 'role' and not self.audience_role:
            raise ValueError("audience_role is required when audience_type is 'role'")
        if self.audience_type == 'user' and not self.target_user_id:
            raise ValueError("target_user_id is required when audience_type is 'user'")
        return self


class NotificationCreate(NotificationBase):
    """
    Schema used by an admin to create a new global/role/private notification.
    """
    pass


class NotificationResponse(NotificationBase):
    """
    Schema for returning full notification details from the API.
    """
    id: uuid.UUID
    read_at: Optional[datetime] = None
    created_by: Optional[uuid.UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UnreadCountResponse(BaseModel):
    unread_count: int
