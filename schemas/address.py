# /schemas/address.py

import uuid
from typing import Optional
from decimal import Decimal

from pydantic import BaseModel, Field

class AddressBase(BaseModel):
    """
    Base schema for an address, containing shared fields.
    """
    address_line_1: str = Field(..., max_length=255, examples=["123 Anna Salai"])
    address_line_2: Optional[str] = Field(None, max_length=255, examples=["Near Gemini Circle"])
    city: str = Field(..., max_length=100, examples=["Chennai"])
    state: str = Field(..., max_length=100, examples=["Tamil Nadu"])
    pincode: str = Field(..., max_length=20, examples=["600006"])
    country: str = Field("India", max_length=100)
    latitude: Optional[Decimal] = Field(
        None, 
        ge=-90, 
        le=90, 
        description="Latitude of the address", 
        examples=[13.0610]
    )
    longitude: Optional[Decimal] = Field(
        None, 
        ge=-180, 
        le=180, 
        description="Longitude of the address", 
        examples=[80.2497]
    )
    is_primary: bool = Field(False, description="Whether this is the primary address for the user")

class AddressCreate(AddressBase):
    """
    Schema for creating a new address. Inherits all fields from AddressBase.
    This schema is used for request body validation when a new address is posted.
    """
    # No additional fields are needed for creation beyond what's in the base.
    pass


class AddressUpdate(BaseModel):
    """
    Schema for updating an existing address. All fields are optional to allow
    for partial updates (e.g., updating only the pincode).
    """
    address_line_1: Optional[str] = Field(None, max_length=255)
    address_line_2: Optional[str] = Field(None, max_length=255)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    pincode: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field(None, max_length=100)
    latitude: Optional[Decimal] = Field(None, ge=-90, le=90)
    longitude: Optional[Decimal] = Field(None, ge=-180, le=180)
    is_primary: Optional[bool] = None


class AddressResponse(AddressBase):
    """
    Schema for returning an address from the API.
    This includes database-generated fields like `id`.
    """
    id: uuid.UUID
    user_id: Optional[uuid.UUID]
    is_primary: bool

    class Config:
        """
        Pydantic configuration to allow creating the schema from an ORM model instance.
        """
        from_attributes = True