import uuid
from datetime import time
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import select

import models


class WorkingHoursRepository:
    """Repository for handling working hours database operations."""

    def __init__(self, db: Session):
        """Initializes the repository with a SQLAlchemy session."""
        self.db = db

    def create(self, *, nurse_id : uuid.UUID, working_hours_in: Dict[str, Any]) -> models.WorkingHours:
        """Create a new working hours record.

        Args:
            working_hours_in (Dict[str, Any]): Input data for a new
                `WorkingHours` record.

        Returns:
            models.WorkingHours: The created working hours ORM object.
        """
        data = {**working_hours_in,"nurse_id" : nurse_id}
        db_working_hours = models.WorkingHours(**data)

        self.db.add(db_working_hours)
        self.db.commit()
        self.db.refresh(db_working_hours)
        return db_working_hours


    def bulk_create(self, *, nurse_id : uuid.UUID , working_hours_data: List[Dict[str, Any]]) -> List[models.WorkingHours]:
        """Insert multiple working hours records in a single transaction.

        Args:
            working_hours_data (List[Dict[str, Any]]): List of input dictionaries
                for `WorkingHours` rows.

        Returns:
            List[models.WorkingHours]: The created working hours ORM objects.
        """
        working_hours = [{**data,"nurse_id" : nurse_id} for data in working_hours_data]
        db_working_hours = [models.WorkingHours(**data) for data in working_hours]
        self.db.add_all(db_working_hours)
        self.db.commit()
        for item in db_working_hours:
            self.db.refresh(item)
        return db_working_hours

    def get_by_id(self, *, working_hours_id: uuid.UUID) -> Optional[models.WorkingHours]:
        """Retrieve a working hours record by its primary key.

        Args:
            working_hours_id (uuid.UUID): The ID of the working hours record.

        Returns:
            Optional[models.WorkingHours]: The found record or None.
        """

        return self.db.get(models.WorkingHours, working_hours_id)

    def get_for_nurse(self, *, nurse_id: uuid.UUID) -> List[models.WorkingHours]:
        """Fetch all working hours records for a nurse.

        Args:
            nurse_id (uuid.UUID): The nurse's ID.

        Returns:
            List[models.WorkingHours]: All working hours slots for the nurse.
        """

        query = self.db.query(models.WorkingHours).filter(models.WorkingHours.nurse_id == nurse_id)

        return query.all()

    def update(self, *, working_hours_id: uuid.UUID, updates: Dict[str, Any]) -> Optional[models.WorkingHours]:
        """Update a working hours record.

        Args:
            working_hours_id (uuid.UUID): The ID of the record to update.
            updates (Dict[str, Any]): Field updates to apply.

        Returns:
            Optional[models.WorkingHours]: The updated record, or None if not found.
        """

        db_working_hours = self.get_by_id(working_hours_id=working_hours_id)
        if not db_working_hours:
            return None

        for key, value in updates.items():
            setattr(db_working_hours, key, value)

        self.db.add(db_working_hours)
        self.db.commit()
        self.db.refresh(db_working_hours)

        return db_working_hours

    def delete(self, *, working_hours_id: uuid.UUID) -> Optional[models.WorkingHours]:
        """Remove a working hours record from the database.

        Args:
            working_hours_id (uuid.UUID): The ID of the record to delete.

        Returns:
            Optional[models.WorkingHours]: The deleted record, or None if not found.
        """

        db_working_hours = self.get_by_id(working_hours_id=working_hours_id)
        if not db_working_hours:
            return None

        self.db.delete(db_working_hours)
        self.db.commit()

        return db_working_hours

    def find_overlapping(
        self,
        *,
        nurse_id: uuid.UUID,
        day_of_week: int,
        start_time: time,
        end_time: time,
        exclude_working_hours_id: Optional[uuid.UUID] = None,
    ) -> Optional[models.WorkingHours]:
        """Find an overlapping working hours slot for a nurse.

        Args:
            nurse_id (uuid.UUID): Nurse identifier.
            day_of_week (int): Day of week (0=Monday, 6=Sunday).
            start_time (time): Proposed start time.
            end_time (time): Proposed end time.
            exclude_working_hours_id (Optional[uuid.UUID]): If provided, exclude
                this record from overlap checks.

        Returns:
            Optional[models.WorkingHours]: An overlapping slot if one exists.
        """

        query = self.db.query(models.WorkingHours).filter(
            models.WorkingHours.nurse_id == nurse_id,
            models.WorkingHours.day_of_week == day_of_week,
            models.WorkingHours.start_time < end_time,
            models.WorkingHours.end_time > start_time,
        )

        if exclude_working_hours_id:
            query = query.filter(models.WorkingHours.id != exclude_working_hours_id)

        return query.first()

