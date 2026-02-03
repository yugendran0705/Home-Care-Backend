# /repositories/availability.py

import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import select, and_

import models
from schemas.availability import AvailabilityCreate # Assumes you will create this schema


class AvailabilityRepository:
    """
    Repository for handling all direct database operations for the Availability model.
    """

    def __init__(self, db: Session):
        """
        Initializes the repository with a database session.
        """
        self.db = db

    def add_slot(self, *, availability_in: AvailabilityCreate) -> models.Availability:
        """
        Adds a new availability slot for a nurse.

        Args:
            availability_in (AvailabilityCreate): A Pydantic schema with nurse_id,
                                                  start_time, and end_time.

        Returns:
            models.Availability: The newly created Availability ORM object.
        """
        db_availability = models.Availability(**availability_in.model_dump())
        
        self.db.add(db_availability)
        self.db.commit()
        self.db.refresh(db_availability)
        return db_availability

    def get_by_id(self, *, availability_id: uuid.UUID) -> Optional[models.Availability]:
        """
        Retrieves a specific availability slot by its ID.

        Args:
            availability_id (uuid.UUID): The ID of the availability slot.

        Returns:
            Optional[models.Availability]: The Availability object if found, otherwise None.
        """
        return self.db.get(models.Availability, availability_id)

    def get_slots_for_nurse(
        self,
        *,
        nurse_id: uuid.UUID,
        start_range: Optional[datetime] = None,
        end_range: Optional[datetime] = None,
        only_available: bool = False
    ) -> List[models.Availability]:
        """
        Retrieves all availability slots for a specific nurse, with optional filters.

        Args:
            nurse_id (uuid.UUID): The ID of the nurse.
            start_range (Optional[datetime]): The start of the time window to search within.
            end_range (Optional[datetime]): The end of the time window to search within.
            only_available (bool): If True, only returns slots where `is_booked` is False.

        Returns:
            List[models.Availability]: A list of the nurse's availability slots.
        """
        query = select(models.Availability).where(models.Availability.nurse_id == nurse_id)

        if start_range:
            query = query.where(models.Availability.start_time >= start_range)
        if end_range:
            query = query.where(models.Availability.end_time <= end_range)
        if only_available:
            query = query.where(models.Availability.is_booked == False)
            
        return self.db.execute(query).scalars().all()

    def update_slot(self, *, availability_id: uuid.UUID, updates: Dict[str, Any]) -> Optional[models.Availability]:
        """
        Updates an availability slot (e.g., to mark it as booked).

        Args:
            availability_id (uuid.UUID): The ID of the slot to update.
            updates (Dict[str, Any]): A dictionary of fields to update.

        Returns:
            Optional[models.Availability]: The updated Availability object, or None if not found.
        """
        db_availability = self.get_by_id(availability_id=availability_id)
        if not db_availability:
            return None
            
        for key, value in updates.items():
            setattr(db_availability, key, value)
            
        self.db.add(db_availability)
        self.db.commit()
        self.db.refresh(db_availability)
        return db_availability

    def delete_slot(self, *, availability_id: uuid.UUID) -> bool:
        """
        Deletes an availability slot.

        Args:
            availability_id (uuid.UUID): The ID of the slot to delete.

        Returns:
            bool: True if the slot was found and deleted, False otherwise.
        """
        db_availability = self.get_by_id(availability_id=availability_id)
        if not db_availability:
            return False
            
        self.db.delete(db_availability)
        self.db.commit()
        return True
