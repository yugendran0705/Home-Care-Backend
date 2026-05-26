# /schemas/nurse_service.py

import uuid
from typing import List

from pydantic import BaseModel, Field

# Import other schemas for nesting in responses
from .nurses import NurseResponse
from .nursing_services import NursingServiceResponse


class NurseServiceBase(BaseModel):
    """
    Base schema for the nurse-service link.
    """
    service_id: uuid.UUID

class NurseServiceBulkCreate(BaseModel):
    """
    Schema for assigning multiple services to a single nurse.
    """
    service_ids: List[uuid.UUID] = Field(
        ...,
        min_length=1,
        description="A list of service IDs to link to the nurse."
    )

class NurseServicesResponse(BaseModel):
    """
    Nested response schema containing nurse profile and service list.
    """
    nurse: NurseResponse
    services: List[NursingServiceResponse]

    class Config:
        from_attributes = True