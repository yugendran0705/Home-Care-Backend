# /views/bookings.py

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

