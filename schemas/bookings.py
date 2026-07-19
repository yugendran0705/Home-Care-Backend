# /schemas/booking.py

import uuid
from datetime import datetime
from typing import Optional
from decimal import Decimal

from pydantic import BaseModel, Field, ValidationInfo, field_validator

# Import other schemas for nesting in the response
from .patients import PatientResponse
from .nurses import NurseResponse
from .nursing_services import NursingServiceResponse
from .address import Address as AddressResponse
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
    parent_booking_id: Optional[uuid.UUID] = None

    @field_validator('scheduled_end_time')
    @classmethod
    def end_time_must_be_after_start_time(
        cls,
        v: datetime,
        info: ValidationInfo
    ) -> datetime:
        start_time = info.data.get('scheduled_start_time')
        if start_time and v <= start_time:
            raise ValueError('Scheduled end time must be after start time')
        return v


class BookingCreate(BookingBase):
    """
    Schema used for creating a new booking.

    booking_status and payment_status are intentionally not fields here: the
    Booking model defaults both to 'Pending', and creation should never let a
    caller set them directly.
    """
    is_parent_booking: bool = False


class PendingBookingRequest(BaseModel):
    """
    Schema for a patient's booking request. scheduled_end_time and
    total_amount are intentionally absent - BookingService derives them from
    the service's duration/duration_type/shift_duration_hours and base_price,
    so a caller can't misstate either. patient_id and parent_booking_id are
    also not fields: patient_id comes from the authenticated user, and
    parent_booking_id is an internal linkage BookingService sets itself when
    it creates a Daily_Shift booking's child rows - a client has no legitimate
    reason to set it and allowing it would let a caller attach a bogus link to
    someone else's booking.
    """
    nurse_id: uuid.UUID
    service_id: uuid.UUID
    scheduled_start_time: datetime = Field(
        ..., description="Desired start timestamp (ISO 8601). Naive values are treated as IST."
    )
    booking_address_id: uuid.UUID
    notes: Optional[str] = None


class PendingBookingResponse(BaseModel):
    """Response for a successfully created pending booking + its pending payment."""
    booking: BookingResponse
    payment: PaymentResponse

    class Config:
        from_attributes = True


class PaymentCallbackRequest(BaseModel):
    """
    Schema for the payment-gateway callback/webhook that confirms or fails a
    booking's payment. In production this would be validated against the
    gateway's own webhook payload/signature rather than trusted as-is.
    """
    transaction_id: Optional[str] = None
    payment_method: Optional[str] = None


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
    service: NursingServiceResponse
    booking_address: AddressResponse
    review: Optional[ReviewResponse] = None
    payment: Optional[PaymentResponse] = None

    class Config:
        from_attributes = True

