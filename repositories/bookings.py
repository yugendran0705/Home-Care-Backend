# /repositories/bookings.py

import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import select

import models
from schemas.bookings import BookingCreate # Assumes you will create this schema


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
