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
    Schema for a patient's booking request. patient_id, parent_booking_id,
    booking_address_id, scheduled_end_time, and total_amount are all
    server-derived, not client-supplied - each would otherwise let a caller
    spoof another user's identity, booking, address, or price.
    """
    nurse_id: uuid.UUID
    service_id: uuid.UUID
    scheduled_start_time: datetime = Field(
        ..., description="Desired start timestamp (ISO 8601). Naive values are treated as IST."
    )
    notes: Optional[str] = None




class BookingCompletionOtpResponse(BaseModel):
    """
    The handover code for a single visit. Only ever returned to the patient
    who owns the booking - the nurse learns it from the patient in person.
    """
    booking_id: uuid.UUID
    completion_otp: str


class CompleteBookingRequest(BaseModel):
    """
    The code the nurse collects from the patient at the end of the visit.
    """
    otp: str = Field(
        ...,
        pattern=r"^\d{6}$",
        description="The 6-digit code shown in the patient's app for this booking.",
    )


class CancellationQuoteResponse(BaseModel):
    """
    What cancelling a booking right now would do, shown to the patient before
    they confirm. Computed by the same code path that performs the cancel.
    """
    booking_id: uuid.UUID
    cancellable: bool
    reason: Optional[str] = Field(None, description="Why it can't be cancelled, when cancellable is false.")
    visits_to_cancel: int = 0
    full_refund_visits: int = 0
    partial_refund_visits: int = 0
    refund_amount: Decimal = Decimal("0.00")
    currency: str = "INR"
    policy: str


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

class PendingBookingResponse(BaseModel):
    """
    Response for a successfully created pending booking + its pending payment.
    payment.gateway_order_id is the Razorpay order id; combined with
    razorpay_key_id, amount, and currency, the frontend has everything it
    needs to open Razorpay Checkout.
    """
    booking: BookingResponse
    payment: PaymentResponse
    razorpay_key_id: str

    class Config:
        from_attributes = True

