# /schemas/booking.py

import uuid
from datetime import datetime
from typing import Optional
from decimal import Decimal

from pydantic import BaseModel, Field, validator

# Import other schemas for nesting in the response
from .patients import PatientResponse
from .nurses import NurseResponse
from .services import ServiceResponse
from .address import AddressResponse
# The following are placeholders; you would create these schemas as well
from .reviews import ReviewResponse
from .payments import PaymentResponse


class BookingBase(BaseModel):
    """
    Base schema for a booking, containing the core fields provided during creation.
    """
    patient_id: uuid.UUID
    nurse_id: uuid.UUID
    service_id: uuid.UUID
    scheduled_start_time: datetime
    scheduled_end_time: datetime
    total_amount: Decimal = Field(..., gt=0, decimal_places=2)
    booking_address_id: uuid.UUID
    notes: Optional[str] = None

    @validator('scheduled_end_time')
    def end_time_must_be_after_start_time(cls, v, values):
        if 'scheduled_start_time' in values and v <= values['scheduled_start_time']:
            raise ValueError('Scheduled end time must be after start time')
        return v


class BookingCreate(BookingBase):
    """
    Schema used for creating a new booking.
    """
    pass


class BookingUpdate(BaseModel):
    """
    Schema for updating a booking. All fields are optional.
    Primarily used by nurses or admins to change the status.
    """
    booking_status: Optional[str] = Field(None, examples=["Confirmed", "Completed", "Cancelled"])
    payment_status: Optional[str] = Field(None, examples=["Paid", "Refunded"])


class BookingResponse(BookingBase):
    """
    Schema for returning full booking details from the API.
    Includes database-generated fields and nested objects for related models.
    """
    id: uuid.UUID
    booking_time: datetime
    booking_status: str
    payment_status: str

    # Nested response objects for rich context
    patient: PatientResponse
    nurse: NurseResponse
    service: ServiceResponse
    booking_address: AddressResponse
    review: Optional[ReviewResponse] = None
    payment: Optional[PaymentResponse] = None

    class Config:
        from_attributes = True

