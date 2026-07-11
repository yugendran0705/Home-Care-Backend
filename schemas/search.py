# schemas/search.py
from pydantic import BaseModel, Field, ValidationInfo, field_validator
from datetime import datetime
import uuid
from typing import Optional

class NurseSearchRequest(BaseModel):
    service_id: uuid.UUID
    patient_latitude: float = Field(..., ge=-90, le=90, description="Patient's current latitude")
    patient_longitude: float = Field(..., ge=-180, le=180, description="Patient's current longitude")
    requested_start_time: datetime = Field(..., description="Desired start timestamp (ISO 8601 format)")
    requested_end_time: datetime = Field(..., description="Desired end timestamp (ISO 8601 format)")
    radius_meters: Optional[int] = Field(8000, ge=1000, le=50000, description="Search radius in meters (Default 8KM)")

    @field_validator('requested_end_time')
    @classmethod
    def verify_time_order(cls, v: datetime, info: ValidationInfo) -> datetime:
        start_time = info.data.get('requested_start_time')
        if start_time and v <= start_time:
            raise ValueError('requested_end_time must be after requested_start_time')
        return v

class NurseSearchResponse(BaseModel):
    nurse_id: uuid.UUID
    first_name: str
    last_name: str
    phone_number: str
    years_of_experience: int
    bio: Optional[str]
    profile_picture_url: Optional[str]
    average_rating: float
    distance_meters: Optional[float] 

    class Config:
        from_attributes = True