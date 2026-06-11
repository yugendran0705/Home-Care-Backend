# schemas/blackout_dates.py

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BlackoutDateBase(BaseModel):
    """
    Shared fields for blackout dates.
    """

    start_datetime: datetime = Field(..., description="Start of the blackout period")

    end_datetime: datetime = Field(..., description="End of the blackout period")

    reason: Optional[str] = Field(None, max_length=255, examples=["Vacation"])


class BlackoutDateCreate(BlackoutDateBase):
    """
    Schema used when creating a blackout date.
    """

    pass


class BlackoutDateUpdate(BaseModel):
    """
    Schema used for partial updates.
    """

    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    reason: Optional[str] = Field(None, max_length=255)


class BlackoutDateResponse(BlackoutDateBase):
    """
    Schema returned from the API.
    """

    id: uuid.UUID
    nurse_id: uuid.UUID

    class Config:
        from_attributes = True
