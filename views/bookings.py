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
    BookingCompletionOtpResponse,
    CompleteBookingRequest,
    CancellationQuoteResponse,
)

router = APIRouter(
    prefix="/bookings",
    tags=["Bookings"],
)

patient_dependency = Depends(RoleChecker(allowed_roles=["Admin", "Patient"]))
nurse_dependency = Depends(RoleChecker(allowed_roles=["Admin", "Nurse"]))
user_dependency = Depends(RoleChecker(allowed_roles=["Admin", "Patient", "Nurse"]))
admin_dependency = Depends(RoleChecker(allowed_roles=["Admin"]))

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


@router.get(
    "/all",
    response_model=List[BookingResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[admin_dependency],
    summary="Get all bookings (Admin Access)",
)
def get_all_bookings(
    skip: int = 0,
    limit: int = 100,
    booking_service: BookingService = Depends(get_booking_service),
):
    """
    Retrieves a paginated list of all bookings. Admin only.
    """
    try:
        return booking_service.list_all_bookings(skip=skip, limit=limit)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve bookings.",
        ) from exc


@router.get(
    "/{booking_id}/completion-otp",
    response_model=BookingCompletionOtpResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the handover code for a booking (Patient only)",
)
def get_completion_otp(
    booking_id: uuid.UUID,
    current_user: models.User = Depends(RoleChecker(allowed_roles=["Patient"])),
    booking_service: BookingService = Depends(get_booking_service),
):
    """
    Returns the code the patient reads out to the nurse once the visit is
    done. Restricted to the patient who owns the booking - deliberately not
    exposed on any other booking response, since the nurse must learn it from
    the patient rather than from the API.
    """
    try:
        booking = booking_service.get_completion_otp(
            booking_id=booking_id, patient_id=current_user.id
        )
        return BookingCompletionOtpResponse(
            booking_id=booking.id, completion_otp=booking.completion_otp
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve the completion code.",
        ) from exc


@router.post(
    "/{booking_id}/completion-otp/regenerate",
    response_model=BookingCompletionOtpResponse,
    status_code=status.HTTP_200_OK,
    summary="Issue a fresh handover code for a booking (Patient only)",
)
def regenerate_completion_otp(
    booking_id: uuid.UUID,
    current_user: models.User = Depends(RoleChecker(allowed_roles=["Patient"])),
    booking_service: BookingService = Depends(get_booking_service),
):
    """
    Issues a new code and clears the attempt lockout. Use this when the nurse
    has exhausted their tries on the previous code; a plain GET of the code
    deliberately does not reset the lockout.
    """
    try:
        booking = booking_service.regenerate_completion_otp(
            booking_id=booking_id, patient_id=current_user.id
        )
        return BookingCompletionOtpResponse(
            booking_id=booking.id, completion_otp=booking.completion_otp
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to regenerate the completion code.",
        ) from exc


@router.get(
    "/{booking_id}/cancellation",
    response_model=CancellationQuoteResponse,
    status_code=status.HTTP_200_OK,
    summary="Preview what cancelling a booking would refund (Patient only)",
)
def get_cancellation_quote(
    booking_id: uuid.UUID,
    current_user: models.User = Depends(RoleChecker(allowed_roles=["Patient"])),
    booking_service: BookingService = Depends(get_booking_service),
):
    """
    Read-only: which visits a cancel would close and the refund it would
    issue right now, so the app can show it before the patient confirms.
    """
    try:
        return booking_service.get_cancellation_quote(
            booking_id=booking_id, patient_id=current_user.id
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to prepare the cancellation.",
        ) from exc


@router.post(
    "/{booking_id}/cancel",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel a booking and refund per the cancellation policy (Patient only)",
)
def cancel_booking(
    booking_id: uuid.UUID,
    current_user: models.User = Depends(RoleChecker(allowed_roles=["Patient"])),
    booking_service: BookingService = Depends(get_booking_service),
):
    """
    Cancels the patient's own booking. Unpaid bookings are simply cancelled;
    paid ones cancel every visit that hasn't started and refund each in full
    (12+ hours' notice) or 50% (less), via Razorpay.
    """
    try:
        return booking_service.cancel_booking(
            booking_id=booking_id, patient_id=current_user.id
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel booking.",
        ) from exc


@router.post(
    "/{booking_id}/complete",
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary="Complete a booking with the patient's handover code (Nurse only)",
)
def complete_booking(
    booking_id: uuid.UUID,
    complete_request: CompleteBookingRequest,
    current_user: models.User = Depends(RoleChecker(allowed_roles=["Nurse"])),
    booking_service: BookingService = Depends(get_booking_service),
):
    """
    Marks the nurse's own booking Completed once they supply the code the
    patient gave them at the end of the visit. Each shift of a multi-day
    booking is completed on its own.
    """
    try:
        return booking_service.complete_booking(
            booking_id=booking_id,
            nurse_id=current_user.id,
            otp=complete_request.otp,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete booking.",
        ) from exc


@router.get(
    "/me",
    response_model=List[BookingResponse],
    status_code=status.HTTP_200_OK,
    summary="Get all bookings for a patient",
)
def get_bookings_for_patient(
    current_user: models.User = user_dependency,
    booking_service: BookingService = Depends(get_booking_service),
):
    """
    User can be either a patient or a nurse. Returns all bookings for the current user.
    """
    try:
        return booking_service.get_bookings_for_user(user_id=current_user.id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve bookings for patient.",
        ) from exc

