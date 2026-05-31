# /schemas/nurse.py

import uuid
from datetime import date
from typing import Optional, List
from decimal import Decimal
from pydantic import BaseModel, EmailStr, Field
from .nursing_services import NursingServiceBase, NursingServiceCreate, NursingServiceUpdate, NursingServiceResponse



# Import other schemas for nesting
from .users import UserResponse
from .address import AddressCreate, Address as AddressResponse


class NurseBase(BaseModel):
    """
    Base schema for a nurse's profile, containing shared fields.
    """
    first_name: str = Field(..., max_length=100, examples=["Priya"])
    last_name: str = Field(..., max_length=100, examples=["Sharma"])
    phone_number: str = Field(..., max_length=20, examples=["9988776655"])
    date_of_birth: Optional[date] = Field(None, examples=["1992-11-15"])
    gender: Optional[str] = Field(None, max_length=10, examples=["Female"])
    license_number: str = Field(..., max_length=50, examples=["TNMC-12345"])
    years_of_experience: int = Field(..., ge=0, examples=[5])
    bio: Optional[str] = Field(None, examples=["Experienced pediatric nurse."])
    profile_picture_url: str = Field(..., examples=["https://example.com/profile.jpg"])

class NurseServiceRegistrationItem(BaseModel):
    """Represents a group of service IDs to register for a nurse."""
    service_ids: List[uuid.UUID] = Field(
        ..., 
        min_length=1,
        description="The list of service IDs to register for this nurse."
    )





class NurseCreate(NurseBase):
    """
    Schema for registering a new nurse. Includes user account credentials,
    an optional address, and optional services.
    """
    email: EmailStr = Field(..., examples=["priya.sharma@example.com"])
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    address: Optional[AddressCreate] = None
    services: Optional[List[NurseServiceRegistrationItem]] = Field(
        None,
        description="Optional list of service IDs to register for the nurse",
        examples=[[{"service_ids": ["550e8400-e29b-41d4-a716-446655440000", "550e8400-e29b-41d4-a716-446655440001"]}]]
    )
    


class NurseUpdate(BaseModel):
    """
    Schema for updating a nurse's profile. All fields are optional
    to allow for partial updates.
    """
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    phone_number: Optional[str] = Field(None, max_length=20)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=10)
    years_of_experience: Optional[int] = Field(None, ge=0)
    bio: Optional[str] = None
    profile_picture_url: Optional[str] = None


class NurseResponse(NurseBase):
    """
    Schema for returning a nurse's profile from the API.
    Includes nested user information and addresses.
    """
    id: uuid.UUID
    is_verified: bool
    average_rating: Decimal
    user: UserResponse
    
    class Config:
        from_attributes = True
        
   

class NurseCreateResponse(BaseModel):
    access_token: str
    refresh_token: str
    nurse: NurseResponse
    services: List[NursingServiceResponse]
    class Config:
        from_attributes = True