# /schemas/payment.py

import uuid
from datetime import datetime
from typing import Optional
from decimal import Decimal

from pydantic import BaseModel, Field



class PaymentBase(BaseModel):
    """Base schema for payment-related operations. Contains common fields used across different payment schemas.
    """
    booking_id: uuid.UUID
    patient_id: uuid.UUID
    amount: Decimal = Field(..., gt=0, decimal_places=2, examples=[1500.50])
    currency: str = Field("INR", max_length=10)


class PaymentCreate(PaymentBase):
    """Used internally to create the Payment row before calling Razorpay Orders API."""
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
    id: uuid.UUID
    payment_status: str
    payment_method: Optional[str] = None   # populated later, so lives here not in Create
    transaction_id: Optional[str] = None
    gateway_order_id: Optional[str] = None
    failure_reason: Optional[str] = None
    refund_id: Optional[str] = None
    refunded_amount: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True



class RazorpayOrderCreate(BaseModel):
    """Input to your endpoint that kicks off payment for a booking."""
    booking_id: uuid.UUID
    patient_id: uuid.UUID
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    currency: str = Field("INR", max_length=10)


class PaymentVerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

class PaymentVerifyResponse(BaseModel):
    payment_id: uuid.UUID
    payment_status: str
    verified: bool


class PaymentUpdate(BaseModel):
    payment_status: Optional[str] = Field(None, examples=["Success", "Failed", "Refunded"])
    transaction_id: Optional[str] = Field(None, max_length=255)
    payment_method: Optional[str] = Field(None, max_length=50)
    gateway_order_id: Optional[str] = None
    failure_reason: Optional[str] = Field(None, max_length=255)
    refund_id: Optional[str] = None
    refunded_amount: Optional[Decimal] = Field(None, decimal_places=2)



class RazorpayWebhookPayload(BaseModel):
    """Shape of the raw envelope Razorpay POSTs to your webhook endpoint."""
    entity: str
    account_id: str
    event: str                     # e.g. "payment.captured"
    contains: list[str]
    payload: dict                  # nested {payment: {entity: {...}}} etc — keep raw
    created_at: int
