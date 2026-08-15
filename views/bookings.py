# /views/bookings.py

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
from config.database import get_db
from utils.roleChecker import RoleChecker
from services.search import SearchService
from services.bookings import BookingService
from schemas.search import NurseSearchRequest, NurseSearchResponse
from schemas.bookings import (
    PendingBookingRequest,
    PendingBookingResponse,
    BookingResponse,
    PaymentCallbackRequest,
)

router = APIRouter(
    prefix="/bookings",
    tags=["Bookings"],
)

patient_dependency = Depends(RoleChecker(allowed_roles=["Admin", "Patient"]))
nurse_dependency = Depends(RoleChecker(allowed_roles=["Admin", "Nurse"]))

# Dependency to provide the SearchService
def get_search_service(db: Session = Depends(get_db)) -> SearchService:
    return SearchService(db)


# Dependency to provide the BookingService
def get_booking_service(db: Session = Depends(get_db)) -> BookingService:
    return BookingService(db)

@router.post(
    "/search",
    response_model=List[NurseSearchResponse],
    status_code=status.HTTP_200_OK,
    summary="Search available nurses for a booking",
)
def search_available_nurses(
    search_request: NurseSearchRequest,
    current_user: models.User = patient_dependency,
    search_service: SearchService = Depends(get_search_service),
):
    """
    Finds available nurses for the requested service, location, and booking window.
    """
    try:
        return search_service.search_available_nurses(
            search_request=search_request, patient_id=current_user.id
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search available nurses.",
        ) from exc


@router.post(
    "/",
    response_model=PendingBookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a pending booking + pending payment for a nurse",
)
def create_booking(
    booking_request: PendingBookingRequest,
    current_user: models.User = patient_dependency,
    booking_service: BookingService = Depends(get_booking_service),
):
    """
    Creates a Pending booking and its Pending Payment, holding the nurse's
    slot for a limited window until payment is confirmed. See
    BookingService.create_booking for the Redis-lock + transaction
    concurrency design.
    """
    try:
        return booking_service.create_booking(
            patient_id=current_user.id,
            nurse_id=booking_request.nurse_id,
            service_id=booking_request.service_id,
            scheduled_start_time=booking_request.scheduled_start_time,
            notes=booking_request.notes,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create booking.",
        ) from exc


@router.post(
    "/{booking_id}/confirm-payment",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Payment gateway webhook: mark payment successful and confirm the booking",
)
def confirm_booking_payment(
    booking_id: uuid.UUID,
    callback: PaymentCallbackRequest,
    booking_service: BookingService = Depends(get_booking_service),
):
    """
    Called by the payment gateway on successful payment. Not user-authenticated
    by design (the gateway calls this, not a logged-in patient); production
    must verify the gateway's webhook signature before trusting the payload.
    """
    try:
        return booking_service.confirm_booking(
            booking_id=booking_id,
            transaction_id=callback.transaction_id,
            payment_method=callback.payment_method,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to confirm booking payment.",
        ) from exc


@router.post(
    "/{booking_id}/fail-payment",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Payment gateway webhook: mark payment failed and cancel the booking",
)
def fail_booking_payment(
    booking_id: uuid.UUID,
    callback: PaymentCallbackRequest,
    booking_service: BookingService = Depends(get_booking_service),
):
    """
    Called by the payment gateway on failed payment. Not user-authenticated -
    see confirm_booking_payment.
    """
    try:
        return booking_service.fail_booking(
            booking_id=booking_id,
            transaction_id=callback.transaction_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fail booking payment.",
        ) from exc


@router.get(
    "/patient/{patient_id}",
    response_model=List[BookingResponse],
    status_code=status.HTTP_200_OK,
    summary="Get all bookings for a patient",
)
def get_bookings_for_patient(
    patient_id: uuid.UUID,
    current_user: models.User = patient_dependency,
    booking_service: BookingService = Depends(get_booking_service),
):
    """
    A Patient may only view their own bookings; Admin may view anyone's.
    """
    if current_user.user_type == "Patient" and current_user.id != patient_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only view your own bookings.",
        )
    try:
        return booking_service.get_bookings_for_patient(patient_id=patient_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve bookings for patient.",
        ) from exc


@router.get(
    "/nurse/{nurse_id}",
    response_model=List[BookingResponse],
    status_code=status.HTTP_200_OK,
    summary="Get all bookings for a nurse",
)
def get_bookings_for_nurse(
    nurse_id: uuid.UUID,
    current_user: models.User = nurse_dependency,
    booking_service: BookingService = Depends(get_booking_service),
):
    """
    A Nurse may only view their own bookings; Admin may view anyone's.
    """
    if current_user.user_type == "Nurse" and current_user.id != nurse_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only view your own bookings.",
        )
    try:
        return booking_service.get_bookings_for_nurse(nurse_id=nurse_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve bookings for nurse.",
        ) from exc
