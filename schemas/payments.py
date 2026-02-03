# /schemas/payment.py

import uuid
from datetime import datetime
from typing import Optional
from decimal import Decimal

from pydantic import BaseModel, Field


class PaymentBase(BaseModel):
    """
    Base schema for payment information.
    """
    booking_id: uuid.UUID
    patient_id: uuid.UUID
    amount: Decimal = Field(..., gt=0, decimal_places=2, examples=[1500.50])
    currency: str = Field("INR", max_length=10)
    payment_method: Optional[str] = Field(None, max_length=50, examples=["Credit Card"])


class PaymentCreate(PaymentBase):
    """
    Schema for creating a new payment record when a booking is initiated.
    """
    # The initial status is set by the model's default, so it's not needed here.
    pass


class PaymentUpdate(BaseModel):
    """
    Schema for updating a payment, typically after a webhook from a payment gateway.
    All fields are optional.
    """
    payment_status: Optional[str] = Field(None, examples=["Success", "Failed"])
    transaction_id: Optional[str] = Field(None, max_length=255)
    payment_method: Optional[str] = Field(None, max_length=50)


class PaymentResponse(PaymentBase):
    """
    Schema for returning payment details from the API.
    Includes database-generated fields.
    """
    id: uuid.UUID
    payment_status: str
    transaction_id: Optional[str] = None
    payment_date: datetime

    class Config:
        from_attributes = True

