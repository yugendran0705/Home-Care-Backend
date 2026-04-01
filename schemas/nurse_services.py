# /schemas/nurse_service.py

import uuid
from typing import List, Optional
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
    Schema for linking a single service to a nurse.
    """
    pass


class NurseServiceBulkCreate(BaseModel):
    """
    Schema for assigning multiple services to a single nurse.
    """
    nurse_id: uuid.UUID
    service_ids: List[uuid.UUID]
    price: Optional[Decimal] = Field(
        None,
        gt=0,
        decimal_places=2,
        description="An optional price to apply for all listed services.",
        examples=[650.00]
    )


class NurseServiceBulkResponse(BaseModel):
    """
    Response schema for a bulk nurse-service assignment.
    """
    nurse_id: uuid.UUID
    service_ids: List[uuid.UUID]


class NurseServiceItem(BaseModel):
    """
    Individual service item for a nurse's service list.
    """
    service: ServiceResponse
    price: Optional[Decimal] = None

    class Config:
        from_attributes = True


class NurseServicesResponse(BaseModel):
    """
    Nested response schema containing nurse profile and service list.
    """
    nurse: NurseResponse
    services: List[NurseServiceItem]

    class Config:
        from_attributes = True


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


class NurseServiceUpdate(BaseModel):
    """
    Schema for updating the price of a nurse-service link.
    """
    price: Decimal = Field(
        ...,
        gt=0,
        decimal_places=2,
        description="The new price for this service by this nurse.",
        examples=[750.00]
    )

