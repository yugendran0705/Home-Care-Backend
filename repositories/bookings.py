# /repositories/bookings.py

import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_

import models
from schemas.bookings import BookingCreate


class BookingRepository:
    """
    Repository for handling all direct database operations for the Booking model.
    """

    def __init__(self, db: Session):
        """
        Initializes the repository with a database session.
        """
        self.db = db

    def create(self, *, booking_in: BookingCreate) -> models.Booking:
        """
        Creates a new booking record in the database.

        Args:
            booking_in (BookingCreate): A Pydantic schema with the new booking data.

        Returns:
            models.Booking: The newly created Booking ORM object.
        """
        db_booking = models.Booking(**booking_in.model_dump())

        self.db.add(db_booking)
        self.db.commit()
        self.db.refresh(db_booking)
        return db_booking

    def bulk_create(self, bookings_data: List[Dict[str, Any]]) -> List[models.Booking]:
        """Inserts multiple bookings in a single transaction."""
        db_bookings = [models.Booking(**data) for data in bookings_data]
        self.db.add_all(db_bookings)
        self.db.commit()
        for db_booking in db_bookings:
            self.db.refresh(db_booking)
        return db_bookings

    def get_by_id(self, *, booking_id: uuid.UUID) -> Optional[models.Booking]:
        """
        Retrieves a booking by its primary key.

        Args:
            booking_id (uuid.UUID): The ID of the booking to retrieve.

        Returns:
            Optional[models.Booking]: The Booking object if found, otherwise None.
        """
        return self.db.get(models.Booking, booking_id)

    def get_for_patient(self, *, patient_id: uuid.UUID) -> List[models.Booking]:
        """
        Retrieves all bookings made by a specific patient.

        Args:
            patient_id (uuid.UUID): The patient's ID.

        Returns:
            List[models.Booking]: A list of the patient's bookings.
        """
        statement = select(models.Booking).where(models.Booking.patient_id == patient_id)
        return self.db.execute(statement).scalars().all()

    def get_for_nurse(self, *, nurse_id: uuid.UUID) -> List[models.Booking]:
        """
        Retrieves all bookings assigned to a specific nurse.

        Args:
            nurse_id (uuid.UUID): The nurse's ID.

        Returns:
            List[models.Booking]: A list of the nurse's bookings.
        """
        statement = select(models.Booking).where(models.Booking.nurse_id == nurse_id)
        return self.db.execute(statement).scalars().all()

    def update(self, *, booking_id: uuid.UUID, updates: Dict[str, Any]) -> Optional[models.Booking]:
        """
        Updates an existing booking's details (e.g., status).

        Args:
            booking_id (uuid.UUID): The ID of the booking to update.
            updates (Dict[str, Any]): A dictionary of fields to update.

        Returns:
            Optional[models.Booking]: The updated Booking object, or None if not found.
        """
        db_booking = self.get_by_id(booking_id=booking_id)
        if not db_booking:
            return None
            
        for key, value in updates.items():
            setattr(db_booking, key, value)
            
        self.db.add(db_booking)
        self.db.commit()
        self.db.refresh(db_booking)
        return db_booking

    def list_all(self, *, skip: int = 0, limit: int = 100) -> List[models.Booking]:
        """
        Retrieves a paginated list of all bookings.

        Args:
            skip (int): The number of records to skip.
            limit (int): The maximum number of records to return.

        Returns:
            List[models.Booking]: A list of Booking objects.
        """
        statement = select(models.Booking).offset(skip).limit(limit)
        return self.db.execute(statement).scalars().all()

    def delete(self, *, booking_id: uuid.UUID) -> Optional[models.Booking]:
        """
        Deletes a booking from the database.
        Note: A soft delete or status change (e.g., to 'Cancelled') is usually
        preferred for booking records and would be handled in the service layer.

        Args:
            booking_id (uuid.UUID): The ID of the booking to delete.

        Returns:
            Optional[models.Booking]: The deleted Booking object, or None if not found.
        """
        db_booking = self.get_by_id(booking_id=booking_id)
        if not db_booking:
            return None

        self.db.delete(db_booking)
        self.db.commit()
        return db_booking

    # ------------------------------------------------------------------
    # No-commit helpers for use inside a service-owned transaction (the
    # pending-booking create flow and the confirm/cancel flows need Booking +
    # Payment writes to commit together atomically, so these do NOT commit —
    # the service calls db.commit()/db.rollback() once, after all writes).
    # ------------------------------------------------------------------

    def add(self, booking: models.Booking) -> models.Booking:
        """Adds a Booking to the session and flushes so booking.id is populated
        immediately (needed for child rows' parent_booking_id FK)."""
        self.db.add(booking)
        self.db.flush()
        return booking

    def add_all(self, bookings: List[models.Booking]) -> List[models.Booking]:
        """Adds multiple Bookings and flushes. No commit."""
        self.db.add_all(bookings)
        self.db.flush()
        return bookings

    def find_conflicting(
        self,
        *,
        nurse_id: uuid.UUID,
        windows: List[Tuple[datetime, datetime]],
        pending_active_since: datetime,
        travel_buffer: timedelta,
    ) -> bool:
        """
        True if the nurse has a Confirmed booking, or an active (not-yet-expired)
        Pending booking, overlapping any of the given (start, end) windows.
        Only child/standalone rows carry real time slots; parent bookings are
        billing wrappers and are excluded.
        """
        status_filter = or_(
            models.Booking.booking_status == "Confirmed",
            and_(
                models.Booking.booking_status == "Pending",
                models.Booking.booking_time >= pending_active_since,
            ),
        )
        overlap_filters = [
            and_(
                models.Booking.scheduled_start_time < end + travel_buffer,
                models.Booking.scheduled_end_time > start - travel_buffer,
            )
            for start, end in windows
        ]
        conflict = (
            self.db.query(models.Booking.id)
            .filter(
                models.Booking.nurse_id == nurse_id,
                models.Booking.is_parent_booking == False,  # noqa: E712
                status_filter,
                or_(*overlap_filters),
            )
            .first()
        )
        return conflict is not None

    def get_for_update(self, *, booking_id: uuid.UUID) -> Optional[models.Booking]:
        """Row-locks the booking (SELECT ... FOR UPDATE) for atomic status transitions."""
        return (
            self.db.query(models.Booking)
            .filter(models.Booking.id == booking_id)
            .with_for_update()
            .one_or_none()
        )

    def set_status(
        self, *, booking: models.Booking, booking_status: str, payment_status: str
    ) -> models.Booking:
        """Mutates status fields on an already-loaded (and typically row-locked)
        booking. No commit — caller controls the transaction boundary."""
        booking.booking_status = booking_status
        booking.payment_status = payment_status
        return booking

    def cascade_children_status(
        self, *, parent_booking_id: uuid.UUID, booking_status: str, payment_status: str
    ) -> None:
        """Bulk-updates all child shifts of a Daily_Shift parent. No commit."""
        self.db.query(models.Booking).filter(
            models.Booking.parent_booking_id == parent_booking_id
        ).update(
            {
                models.Booking.booking_status: booking_status,
                models.Booking.payment_status: payment_status,
            },
            synchronize_session=False,
        )
