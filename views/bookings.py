from fastapi import APIRouter, Depends, HTTPException, status
from schemas.bookings import *
from config.database import get_db
from services.bookings import BookingService
from utils.roleChecker import RoleChecker
import models
from typing import List

router = APIRouter(prefix="/bookings", tags=["bookings"])


def get_bookings_service(db=Depends(get_db)):
    return BookingService(db)


patient_dependency = Depends(RoleChecker(allowed_roles=["Admin", "Patient"]))
nurse_dependency = Depends(RoleChecker(allowed_roles=["Nurse", "Admin"]))
admin_dependency = Depends(RoleChecker(allowed_roles=["Admin"]))
user_dependency = Depends(RoleChecker(allowed_roles=["Patient", "Nurse", "Admin"]))


@router.post(
    "/",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new booking",
)
def create_new_booking(
    booking_in: BookingCreate,
    service: BookingService = Depends(get_bookings_service),
    current_user: models.User = patient_dependency,
):
    """
    Handles the creation of a new booking and associates it with the respective nurse and patient.
    """
    try:
        new_booking = service.create_booking(booking_in=booking_in)
    except Exception as e:
        print(f"Error:{e}")
        raise HTTPException(status_code=500, detail=f"Error in creating booking: {e}")

    return new_booking


@router.get(
    "/patient",
    response_model=List[BookingResponse],
    summary="Returns a list of bookings associted with a specific patient",
)
def get_bookings_for_patient(
    service: BookingService = Depends(get_bookings_service),
    current_user: models.User = patient_dependency,
):
    """Retrieves all the bookings associted with the authenticated patient"""
    try:
        return service.get_bookings_for_patient(patient_id=current_user.id)
    except Exception as e:
        print(f"Error fetching bookings {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error in fetching bookings {e}",
        )


@router.get(
    "/nurse",
    response_model=List[BookingResponse],
    summary="Returns a list of bookings associted with a specific nurse",
)
def get_bookings_for_nurse(
    service: BookingService = Depends(get_bookings_service),
    current_user: models.User = nurse_dependency,
):
    """Retrieves all the bookings associted with the authenticated nurse"""
    try:
        return service.get_bookings_for_nurse(nurse_id=current_user.id)
    except Exception as e:
        print(f"Error fetching bookings {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error in fetching bookings {e}",
        )


@router.put(
    "/{booking_id}",
    response_model=BookingResponse,
    summary="Updates an existing booking(Admin Access)",
    dependencies=[admin_dependency],
)
def update_booking(
    booking_id: uuid.UUID,
    booking_update_data: BookingUpdateAdmin,
    service: BookingService = Depends(get_bookings_service),
):
    """
    Updates the details of an existing booking.
    Requires 'Admin' role.
    """
    updated_booking = service.update_booking_admin(
        booking_id=booking_id, booking_in=booking_update_data
    )
    if not updated_booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found"
        )
    return updated_booking


@router.get(
    "/all",
    response_model=List[BookingResponse],
    summary="Returns all the bookings(Admin Access)",
    dependencies=[admin_dependency],
)
def get_all_bookings(
    skip: int = 0,
    limit: int = 100,
    service: BookingService = Depends(get_bookings_service),
):
    """Retrieves all the bookings with pagination. Requires 'Admin' role."""
    bookings = service.get_all_bookings(skip=skip, limit=limit)
    return bookings


@router.patch("/confirm", response_model=BookingResponse, summary="Confirms a booking")
def confirm_booking(
    booking_id: uuid.UUID,
    service: BookingService = Depends(get_bookings_service),
    current_user: models.User = nurse_dependency,
):
    """Confirms a booking by changing its status to 'Confirmed'. Only the nurse associated with the booking can confirm it, and the booking must be in 'Pending' status."""
    current_booking = service.get_booking_by_id(booking_id=booking_id)
    try:
        if not current_booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found"
            )
        if current_booking.nurse_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not authorized to change this booking's status",
            )
        if current_booking.booking_status != "Pending":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Booking cannot be confirmed as it is already cancelled/confirmed/completed",
            )
        updates = BookingUpdate(booking_status="Confirmed")
        updated_booking = service.update_booking(
            booking_id=current_booking.id, booking_in=updates
        )
        return updated_booking
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error changing booking status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occured while changing booking status",
        )


@router.patch("/cancel", response_model=BookingResponse, summary="Cancels a booking")
def cancel_booking(
    booking_id: uuid.UUID,
    service: BookingService = Depends(get_bookings_service),
    current_user: models.User = user_dependency,
):
    """Cancels a booking by changing its status to 'Cancelled'. Both the nurse and patient associated with the booking can cancel it, and the booking must be in 'Pending' or 'Confirmed' status."""
    current_booking = service.get_booking_by_id(booking_id=booking_id)
    allowed_to_change = ["Pending", "Confirmed"]
    try:
        if not current_booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found"
            )
        if (
            current_booking.nurse_id != current_user.id
            and current_booking.patient_id != current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not authorized to change this booking's status",
            )
        if current_booking.booking_status not in allowed_to_change:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Booking cannot be cancelled as it is already cancelled/completed",
            )
        updates = BookingUpdate(booking_status="Cancelled")
        updated_booking = service.update_booking(
            booking_id=booking_id, booking_in=updates
        )
        return updated_booking
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Uexpected error in changing booking status",
        )


@router.delete(
    "/{booking_id}",
    response_model=BookingResponse,
    summary="Deletes a booking(Admin Access)",
    dependencies=[admin_dependency],
)
def delete_booking(
    booking_id: uuid.UUID, service: BookingService = Depends(get_bookings_service)
):
    deleted_booking = service.delete_booking(booking_id=booking_id)
    if not deleted_booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found"
        )
    return deleted_booking


@router.path(
    "/completed", response_model=BookingResponse, summary="Marks a booking as completed"
)
def complete_booking(
    booking_id: uuid.UUID,
    service: BookingService = Depends(get_bookings_service),
    current_user: models.User = nurse_dependency,
):
    """Marks a booking as completed by changing its status to 'Completed'. Only the nurse associated with the booking can mark it as completed, and the booking must be in 'Confirmed' status."""
    current_booking = service.get_booking_by_id(booking_id=booking_id)
    try:
        if not current_booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found"
            )
        if current_booking.nurse_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not authorized to change this booking's status",
            )
        if current_booking.booking_status != "Confirmed":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Booking cannot be marked as completed as it is not in confirmed status",
            )
        updates = BookingUpdate(booking_status="Completed")
        updated_booking = service.update_booking(
            booking_id=current_booking.id, booking_in=updates
        )
        return updated_booking
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error changing booking status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occured while changing booking status",
        )
