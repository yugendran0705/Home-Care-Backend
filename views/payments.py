import uuid
from fastapi import Depends, HTTPException, status, APIRouter
from typing import List

from config.database import get_db
from utils.roleChecker import RoleChecker
from services.payments import PaymentService
import models
from schemas.payments import PaymentCreate, PaymentUpdate, PaymentResponse

# Create API router
router = APIRouter(
    prefix="/payments",
    tags=["Payments"]
)

# Dependency to provide the PaymentService
def get_payment_service(db=Depends(get_db)) -> PaymentService:
    return PaymentService(db)

admin_dependency = Depends(RoleChecker(allowed_roles=["Admin"]))

@router.post(
    "/",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new payment record (Admin Access)"
)
def create_payment_record(
    payment_in: PaymentCreate,
    service: PaymentService = Depends(get_payment_service)
):
    """
    Handles the creation of a new payment record.
    """
    try:
        payment = service.create_payment(payment_in=payment_in)
        if not payment:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create payment record")
        return payment
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create payment record")
    
@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
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
    except Exception as e:
        print(f"Error fetching payment details for ID {payment_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve payment details")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
@router.get(
    "/booking/{booking_id}",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
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
    except Exception as e:
        print(f"Error fetching payment details for booking ID {booking_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve payment details")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    

@router.get(
    "/patient/{patient_id}",
    response_model=List[PaymentResponse],
    status_code=status.HTTP_200_OK,
    summary="Get all payments for a patient by patient ID (Admin Access)"
)
def get_payments_by_patient_id(
    patient_id: uuid.UUID,
    service: PaymentService = Depends(get_payment_service)
):
    """
    Retrieves all payments for a patient by patient ID.
    """
    try:
        payments = service.get_payment_by_patient_id(patient_id=patient_id)
        if not payments:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No payments found for the specified patient")
        return payments
    except Exception as e:
        print(f"Error fetching payments for patient ID {patient_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve payment details")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    

@router.put(
    "/{payment_id}",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
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
    except Exception as e:
        print(f"Error updating payment status for ID {payment_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update payment status")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))    
    

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
    except Exception as e:
        print(f"Error fetching all payments: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve payment details")
    
@router.delete(
    "/{payment_id}",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
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
    except Exception as e:
        print(f"Error deleting payment record for ID {payment_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete payment record")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    

