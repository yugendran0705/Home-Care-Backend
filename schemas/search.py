# schemas/search.py
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
from typing import Optional

class NurseSearchRequest(BaseModel):
    """
    patient_latitude/patient_longitude are intentionally not fields: the search
    is anchored to the authenticated patient's primary Address, looked up
    server-side, so a caller can't search from an arbitrary/spoofed location.
    """
    service_id: uuid.UUID
    requested_start_time: datetime = Field(..., description="Desired start timestamp (ISO 8601 format)")
    radius_meters: Optional[int] = Field(8000, ge=1000, le=50000, description="Search radius in meters (Default 8KM)")

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