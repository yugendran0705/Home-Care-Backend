import uuid
from datetime import time
from typing import Optional

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from schemas.nurses import NursePublicResponse
from utils.scheduling import to_local_wall_time

class WorkingHoursBase(BaseModel):
    """Base schema for working-hours data.
    """

    day_of_week: int = Field(..., ge=0, le=6, description="Day of week (0-6)", examples=[0, 1])
    start_time: time = Field(..., description="Start time for the working slot")
    end_time: time = Field(..., description="End time for the working slot")
    

    # Declared before the end-after-start check so that check compares the
    # already-normalized local times.
    @field_validator('start_time', 'end_time')
    @classmethod
    def normalize_to_local_time(cls, v: time) -> time:
        return to_local_wall_time(v)

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

    @field_validator('start_time', 'end_time')
    @classmethod
    def normalize_to_local_time(cls, v: Optional[time]) -> Optional[time]:
        return to_local_wall_time(v) if v is not None else v



class WorkingHoursResponse(WorkingHoursBase):
    """Response schema returned by the API for a single working-hours record."""

    id: uuid.UUID
    nurse_id: uuid.UUID
    nurse: NursePublicResponse
    is_active: bool = Field(..., description="Whether this working slot is active")

    class Config:
        from_attributes = True


class WorkingHoursListItemResponse(WorkingHoursBase):
    """Response schema for each working-hours item in the list."""

    id: uuid.UUID
    nurse_id: uuid.UUID
    is_active: bool = Field(..., description="Whether this working slot is active")

    class Config:
        from_attributes = True


class NurseWorkingHoursResponse(BaseModel):
    """Response schema for the nurse working-hours collection endpoint."""

    nurse: Optional[NursePublicResponse] = None
    working_hours: list[WorkingHoursListItemResponse]

    class Config:
        from_attributes = True
