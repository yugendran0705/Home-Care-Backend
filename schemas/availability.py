# /schemas/availability.py

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, validator


class AvailabilityBase(BaseModel):
    """
    Base schema for a nurse's availability slot.
    """
    nurse_id: uuid.UUID
    start_time: datetime
    end_time: datetime

    @validator('end_time')
    def end_time_must_be_after_start_time(cls, v, values):
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('End time must be after start time')
        return v


class AvailabilityCreate(AvailabilityBase):
    """
    Schema for creating a new availability slot.
    """
    pass


class AvailabilityUpdate(BaseModel):
    """
    Schema for updating an availability slot. All fields are optional.
    """
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    is_booked: Optional[bool] = None

    @validator('end_time')
    def end_time_must_be_after_start_time(cls, v, values):
        if 'start_time' in values and v and values['start_time'] and v <= values['start_time']:
            raise ValueError('End time must be after start time')
        return v


class AvailabilityResponse(AvailabilityBase):
    """
    Schema for returning availability information from the API.
    """
    id: uuid.UUID
    is_booked: bool

    class Config:
        from_attributes = True

