# /schemas/nurse_service.py

import uuid
from typing import List

from pydantic import BaseModel, Field

# Import other schemas for nesting in responses
from .nurses import NurseResponse, NursePublicResponse
from .nursing_services import NursingServiceResponse


class NurseAssociatedServiceBase(BaseModel):
    """
    Base schema for the nurse-service link.
    """
    service_id: uuid.UUID

class NurseAssociatedServiceBulkCreate(BaseModel):
    """
    Schema for assigning multiple services to a single nurse.
    """
    service_ids: List[uuid.UUID] = Field(
        ...,
        min_length=1,
        description="A list of service IDs to link to the nurse."
    )

class NurseAssociatedServicesResponse(BaseModel):
    """
    Nested response schema containing nurse profile and service list.
    """
    nurse: NurseResponse
    services: List[NursingServiceResponse]

    class Config:
        from_attributes = True


class NursePublicAssociatedServicesResponse(BaseModel):
    """
    Public-safe variant of NurseAssociatedServicesResponse, used where the
    viewer (e.g. a Patient) is not authorized to see account/contact PII.
    """
    nurse: NursePublicResponse
    services: List[NursingServiceResponse]

    class Config:
        from_attributes = True