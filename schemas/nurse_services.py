# /schemas/nurse_service.py

import uuid
from typing import Optional
from decimal import Decimal

from pydantic import BaseModel, Field

# Import other schemas for nesting in responses
from .nurses import NurseResponse
from .services import ServiceResponse


class NurseServiceBase(BaseModel):
    """
    Base schema for the nurse-service link.
    """
    nurse_id: uuid.UUID
    service_id: uuid.UUID
    price: Optional[Decimal] = Field(
        None,
        gt=0,
        decimal_places=2,
        description="A custom price for this service by this specific nurse. If null, the service's base price is used.",
        examples=[650.00]
    )


class NurseServiceCreate(NurseServiceBase):
    """
    Schema for linking a service to a nurse.
    """
    pass


class NurseServiceResponse(NurseServiceBase):
    """
    Schema for returning the nurse-service link from the API.
    This provides full details of both the nurse and the service.
    """
    # Nest the full response schemas for nurse and service
    nurse: NurseResponse
    service: ServiceResponse

    class Config:
        from_attributes = True

