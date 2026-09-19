import json
import uuid
from fastapi import Depends, HTTPException, Request, status, APIRouter
from typing import List

from config.database import get_db
from config.razorpay import RAZORPAY_WEBHOOK_SECRET
from utils.roleChecker import RoleChecker
from utils.logger import logger
from services.payments import PaymentService
import models
from schemas.payments import (
    PaymentUpdate,
    PaymentResponse,
    PaymentVerifyRequest,
    PaymentVerifyResponse,
)

# Create API router
router = APIRouter(
    prefix="/payments",
    tags=["Payments"]
)

# Dependency to provide the PaymentService
def get_payment_service(db=Depends(get_db)) -> PaymentService:
    return PaymentService(db)

admin_dependency = Depends(RoleChecker(allowed_roles=["Admin"]))
patient_dependency = Depends(RoleChecker(allowed_roles=["Admin", "Patient"]))


# A Payment row is only ever created as part of booking creation
# (BookingService.create_booking) or PaymentService.create_order - never
# directly via the API, so there's no standalone "create payment" route here.

@router.post(
    "/verify",
    response_model=PaymentVerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify a Razorpay Checkout success callback (fast UI feedback only)",
)
def verify_checkout(
    verify_in: PaymentVerifyRequest,
    current_user: models.User = patient_dependency,
    service: PaymentService = Depends(get_payment_service),
):
    """
    Called by the frontend right after Razorpay Checkout's handler fires with
    razorpay_order_id/razorpay_payment_id/razorpay_signature. This gives the
    UI immediate feedback; the webhook below is still the source of truth
    that actually confirms the booking.
    """
    try:
        return service.verify_checkout(verify_in=verify_in)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify payment.",
        ) from exc


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Razorpay webhook receiver (payment.captured / payment.failed)",
)
async def razorpay_webhook(
    request: Request,
    service: PaymentService = Depends(get_payment_service),
):
    """
    Called directly by Razorpay, not by the frontend - intentionally
    unauthenticated (no logged-in user calls this), trust instead comes from
    verifying X-Razorpay-Signature against RAZORPAY_WEBHOOK_SECRET.
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    try:
        parsed_payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed webhook payload.",
        ) from exc

    try:
        service.handle_webhook(
            payload_body=raw_body.decode("utf-8"),
            signature=signature,
            webhook_secret=RAZORPAY_WEBHOOK_SECRET,
            parsed_payload=parsed_payload,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook.",
        ) from exc

    return {"status": "ok"}


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[admin_dependency],
    summary="Get payment details by payment ID (Admin Access)"
)
def get_payment_details_by_id(
    payment_id: uuid.UUID,
    service: PaymentService = Depends(get_payment_service)
):
    """
    Retrieves payment details by payment ID.
    """
    try:
        payment = service.get_payment_by_id(payment_id=payment_id)
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        return payment
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        logger.exception("Error fetching payment details for ID %s", payment_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve payment details")
    
@router.get(
    "/booking/{booking_id}",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[admin_dependency],
    summary="Get payment details by booking ID (Admin Access)"
)
def get_payment_details_by_booking_id(
    booking_id: uuid.UUID,
    service: PaymentService = Depends(get_payment_service)
):
    """
    Retrieves payment details by booking ID.
    """
    try:
        payment = service.get_payment_by_booking_id(booking_id=booking_id)
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        return payment
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        logger.exception("Error fetching payment details for booking ID %s", booking_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve payment details")
    

@router.get(
    "/patient/me",
    response_model=List[PaymentResponse],
    status_code=status.HTTP_200_OK,
    summary="Get all payments for the current patient (Patient Access)"
)
def get_payments_by_patient_id(
    # patient_id: uuid.UUID,
    current_user: models.User = patient_dependency,  
    service: PaymentService = Depends(get_payment_service)
):
    """
    Retrieves all payments for the current patient.
    """
    try:
        payments = service.get_payment_by_patient_id(patient_id=current_user.id)
        if not payments:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No payments found for the specified patient")
        return payments
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        logger.exception("Error fetching payments for patient ID %s", current_user.id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve payment details")
    

@router.put(
    "/{payment_id}",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[admin_dependency],
    summary="Update payment status by payment ID"
)
def update_payment_status(
    payment_id: uuid.UUID,
    payment_update: PaymentUpdate,
    service: PaymentService = Depends(get_payment_service)
):
    """
    Updates payment status by payment ID.
    """
    try:
        payment = service.update_payment_status(payment_id=payment_id, payment_update=payment_update)
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        return payment
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        logger.exception("Error updating payment status for ID %s", payment_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update payment status")
    

@router.get(
    "/",
    response_model=List[PaymentResponse],
    status_code=status.HTTP_200_OK,
    summary="Get all payments (Admin Access)"
)   
def get_all_payments(
    skip: int = 0,
    limit: int = 100,
    service: PaymentService = Depends(get_payment_service)
):
    """
    Retrieves a list of all payments with pagination.
    """
    try:
        return service.list_all_payments(skip=skip, limit=limit)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error fetching all payments")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve payment details")
    
@router.delete(
    "/{payment_id}",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[admin_dependency],
    summary="Delete a payment record by payment ID (Admin Access)"
)
def delete_payment_record(
    payment_id: uuid.UUID,
    service: PaymentService = Depends(get_payment_service)
):
    """
    Deletes a payment record by payment ID.
    """
    try:
        payment = service.delete_payment(payment_id=payment_id)
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        return payment
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        logger.exception("Error deleting payment record for ID %s", payment_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete payment record")

    

