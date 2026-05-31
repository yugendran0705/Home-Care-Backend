# /schemas/patient.py

import uuid
from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

# Import other schemas for nesting in responses and requests
from .address import AddressCreate, Address as AddressResponse
from .users import UserResponse  # Assumes a UserResponse schema is in schemas/user.py


class PatientBase(BaseModel):
    """
    Base schema containing the core fields of a patient's profile.
    """
    first_name: str = Field(..., min_length=1, max_length=100, examples=["Suresh"])
    last_name: str = Field(..., min_length=1, max_length=100, examples=["Kumar"])
    phone_number: str = Field(..., max_length=20, examples=["9876543210"])
    date_of_birth: Optional[date] = Field(None, description="Patient's date of birth", examples=["1990-08-02"])
    gender: Optional[str] = Field(None, description="Patient's gender", examples=["Male"])


class PatientCreate(PatientBase):
    """
    Schema used for the registration endpoint. It includes user account
    credentials and an optional address, in addition to the base patient profile.
    """
    email: EmailStr = Field(..., examples=["suresh.k@example.com"])
    password: str = Field(
        ...,
        min_length=8,
        description="Password must be at least 8 characters long"
    )
    address: Optional[AddressCreate] = Field(None, description="Patient's primary address (optional)")


class PatientUpdate(BaseModel):
    """
    Schema for updating a patient's profile. All fields are optional to allow
    for partial updates (e.g., only changing the phone number).
    """
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone_number: Optional[str] = Field(None, max_length=20)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    email: Optional[EmailStr] = None # Also allow updating the user's email


class PatientResponse(PatientBase):
    """
    Schema for API responses. This is the public-facing model that structures the
    data sent to the client, including nested user information and addresses.
    """
    id: uuid.UUID
    # Nest the full UserResponse schema to include user details and addresses
    user: UserResponse
    

    class Config:
        """
        Pydantic configuration to allow creating this schema from a SQLAlchemy ORM model.
        """
        from_attributes = True
        
class PatientCreateResponse(BaseModel):
    access_token: str
    refresh_token: str
    patient: PatientResponse
    class Config:
        from_attributes = True