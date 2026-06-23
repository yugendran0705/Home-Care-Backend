import uuid
from datetime import time
from typing import Optional

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from schemas.nurses import NurseResponse
class WorkingHoursBase(BaseModel):
    """Base schema for working-hours data.
    """

    day_of_week: int = Field(..., ge=0, le=6, description="Day of week (0-6)", examples=[0, 1])
    start_time: time = Field(..., description="Start time for the working slot")
    end_time: time = Field(..., description="End time for the working slot")
    

    @field_validator('end_time')
    @classmethod
    def end_time_must_be_after_start_time(
        cls,
        v: time,
        info: ValidationInfo
    ) -> time:
        start_time = info.data.get('start_time')
        if start_time and v <= start_time:
            raise ValueError('End time must be after start time')
        return v


class WorkingHoursCreate(WorkingHoursBase):
    """Schema used when creating a new working-hours record."""


class WorkingHoursUpdate(BaseModel):
    """Schema for partial updates to a working-hours record.

    All fields are optional to support partial updates.
    """

    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_active: Optional[bool] = None



class WorkingHoursResponse(WorkingHoursBase):
    """Response schema returned by the API for working-hours records."""

    id: uuid.UUID
    nurse_id: uuid.UUID
    nurse: NurseResponse
    is_active: bool = Field(..., description="Whether this working slot is active")

    class Config:
        from_attributes = True
