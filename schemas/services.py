# /schemas/service.py

import uuid
from typing import Optional
from decimal import Decimal

from pydantic import BaseModel, Field


class ServiceBase(BaseModel):
    """
    Base schema for a service, containing the core fields.
    """
    service_name: str = Field(..., max_length=100, examples=["Wound Dressing"])
    description: Optional[str] = Field(None, examples=["Professional cleaning and dressing of wounds."])
    base_price: Decimal = Field(..., gt=0, decimal_places=2, examples=[500.00])
    duration : int = Field(..., gt=0, description="Duration of the service in minutes.", examples=[60])
    duration_type: str = Field(..., max_length=50, description="Type of duration (e.g., minutes, hours).", examples=["minutes"])
    is_active: Optional[bool] = Field(True, description="Indicates if the service is currently active.")
    is_qualified: Optional[bool] = Field(False, description="Indicates if the service has been soft-deleted.")


class ServiceCreate(ServiceBase):
    """
    Schema used for creating a new service.
    """
    pass


class ServiceUpdate(BaseModel):
    """
    Schema for updating a service. All fields are optional to allow
    for partial updates.
    """
    service_name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    base_price: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    duration : Optional[int] = Field(None, gt=0, description="Duration of the service in minutes.")
    duration_type: Optional[str] = Field(None, max_length=50, description="Type of duration (e.g., minutes, hours).")
    is_active: Optional[bool] = None
    is_qualified: Optional[bool] = None

    class Config:
        from_attributes = True


class ServiceResponse(ServiceBase):
    """
    Schema for returning service information from the API.
    Includes database-generated fields like `id` and `is_active`.
    """
    id: uuid.UUID

    class Config:
        from_attributes = True

