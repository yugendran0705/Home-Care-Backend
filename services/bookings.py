from sqlalchemy.orm import Session
from repositories.bookings import BookingRepository
from schemas.bookings import *
import models
from fastapi import HTTPException, status
from typing import List


class BookingService:

    def __init__(self, db: Session):

        self.db = db
        self.booking_repo = BookingRepository(db)

    def create_booking(self, *, booking_in: BookingCreate) -> models.Booking:

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

        return self.booking_repo.get_for_patient(patient_id=patient_id)

    def get_bookings_for_nurse(self, *, nurse_id: uuid.UUID) -> List[models.Booking]:

        return self.booking_repo.get_for_nurse(nurse_id=nurse_id)

    def update_booking_admin(
        self, *, booking_id: uuid.UUID, booking_in: BookingUpdateAdmin
    ) -> Optional[models.Booking]:
        """to check if the current user can update the booking"""

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
        """to check if the current user can update the booking"""

        update_data = booking_in.model_dump(exclude_unset=True)
        updated_booking = self.booking_repo.update(
            booking_id=booking_id, updates=update_data
        )
        if not updated_booking:
            return None
        else:
            return updated_booking

    def get_booking_by_id(self, *, booking_id) -> Optional[models.Booking]:
        return self.booking_repo.get_by_id(booking_id=booking_id)

    def get_all_bookings(
        self, *, skip: int = 0, limit: int = 0
    ) -> List[models.Booking]:
        bookings = self.booking_repo.list_all(skip=skip, limit=limit)
        return bookings
