from sqlalchemy.orm import Session
from repositories.bookings import BookingRepository
from schemas.bookings import *
import models
from fastapi import HTTPException, status
from typing import List


class BookingService:
    """
    Service layer for handling bookings-related business logic.
    """

    def __init__(self, db: Session):
        """
        Initializes the service with a database session and a repository instance.
        """

        self.db = db
        self.booking_repo = BookingRepository(db)

    def create_booking(self, *, booking_in: BookingCreate) -> models.Booking:
        """
        Creates a new booking and associates it with the respective user and nurse.
        """

        nurse_bookings = self.booking_repo.get_for_nurse(nurse_id=booking_in.nurse_id)
        for booking in nurse_bookings:
            if (
                booking.scheduled_start_time
                <= booking_in.scheduled_start_time
                <= booking.scheduled_end_time
                or booking.scheduled_start_time
                <= booking_in.scheduled_end_time
                <= booking.scheduled_end_time
                or booking_in.scheduled_start_time
                <= booking.scheduled_start_time
                <= booking.scheduled_end_time
            ):
                raise Exception("Nurse already booked in the selected time!")
        """To be added(ft): Add booking only if the servuce is provided by the nurse """

        booking_service = self.booking_repo.create(booking_in=booking_in)

        return booking_service

    def get_bookings_for_patient(
        self, *, patient_id: uuid.UUID
    ) -> List[models.Booking]:
        """
        Retrieves all bookings associated with a specific patient.
        """
        return self.booking_repo.get_for_patient(patient_id=patient_id)

    def get_bookings_for_nurse(self, *, nurse_id: uuid.UUID) -> List[models.Booking]:
        """
        Retrieves all bookings associated with a specific nurse.
        """
        return self.booking_repo.get_for_nurse(nurse_id=nurse_id)

    def update_booking_admin(
        self, *, booking_id: uuid.UUID, booking_in: BookingUpdateAdmin
    ) -> Optional[models.Booking]:
        """Update booking details with admin privileges, allowing changes to all fields including status."""

        update_data = booking_in.model_dump(exclude_unset=True)
        updated_booking = self.booking_repo.update(
            booking_id=booking_id, updates=update_data
        )
        if not updated_booking:
            return None
        else:
            return updated_booking

    def update_booking(
        self, *, booking_id: uuid.UUID, booking_in: BookingUpdate
    ) -> Optional[models.Booking]:
        """Used to update the booking_status and payment_status fields."""

        update_data = booking_in.model_dump(exclude_unset=True)
        updated_booking = self.booking_repo.update(
            booking_id=booking_id, updates=update_data
        )
        if not updated_booking:
            return None
        else:
            return updated_booking

    def get_booking_by_id(self, *, booking_id: uuid.UUID) -> Optional[models.Booking]:
        """
        Retrieves a single booking by its ID.
        """
        return self.booking_repo.get_by_id(booking_id=booking_id)

    def get_all_bookings(
        self, *, skip: int = 0, limit: int = 0
    ) -> List[models.Booking]:
        """
        Retrieves all bookings with optional pagination.
        """
        bookings = self.booking_repo.list_all(skip=skip, limit=limit)
        return bookings

    def delete_booking(self, *, booking_id: uuid.UUID) -> Optional[models.Booking]:
        """Deletes a booking by its ID"""
        deleted_booking = self.booking_repo.delete(booking_id=booking_id)
