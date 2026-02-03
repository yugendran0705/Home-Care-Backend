# /repositories/nurses.py

import uuid
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import select

# Adjust the import path based on your project structure
import models
from schemas.nurses import NurseCreate # Assumes you will create this schema


class NurseRepository:
    """
    Repository for handling all direct database operations for the Nurse model.
    """

    def __init__(self, db: Session):
        """
        Initializes the repository with a database session.

        Args:
            db (Session): The SQLAlchemy database session.
        """
        self.db = db

    def create(self, *, nurse_data: Dict[str, Any]) -> models.Nurse:
        """
        Creates a new nurse profile record.
        Expects a dictionary of nurse data, including the user_id as 'id'.

        Args:
            nurse_data (Dict[str, Any]): Dictionary containing the nurse's profile information.

        Returns:
            models.Nurse: The newly created Nurse ORM object.
        """
        db_nurse = models.Nurse(**nurse_data)
        self.db.add(db_nurse)
        self.db.commit()
        self.db.refresh(db_nurse)
        return db_nurse

    def get_by_id(self, *, nurse_id: uuid.UUID) -> Optional[models.Nurse]:
        """
        Retrieves a nurse by their primary key (which is also the user_id).

        Args:
            nurse_id (uuid.UUID): The ID of the nurse to retrieve.

        Returns:
            Optional[models.Nurse]: The Nurse object if found, otherwise None.
        """
        return self.db.get(models.Nurse, nurse_id)

    def get_by_license_number(self, *, license_number: str) -> Optional[models.Nurse]:
        """
        Retrieves a nurse by their unique license number.

        Args:
            license_number (str): The nurse's license number.

        Returns:
            Optional[models.Nurse]: The Nurse object if found, otherwise None.
        """
        statement = select(models.Nurse).where(models.Nurse.license_number == license_number)
        return self.db.execute(statement).scalar_one_or_none()

    def update(self, *, nurse_id: uuid.UUID, updates: Dict[str, Any]) -> Optional[models.Nurse]:
        """
        Updates an existing nurse's profile.

        Args:
            nurse_id (uuid.UUID): The ID of the nurse to update.
            updates (Dict[str, Any]): A dictionary of fields to update.

        Returns:
            Optional[models.Nurse]: The updated Nurse object, or None if not found.
        """
        db_nurse = self.get_by_id(nurse_id=nurse_id)
        if not db_nurse:
            return None
            
        for key, value in updates.items():
            setattr(db_nurse, key, value)
            
        self.db.add(db_nurse)
        self.db.commit()
        self.db.refresh(db_nurse)
        return db_nurse

    def list_all(self, *, skip: int = 0, limit: int = 100) -> List[models.Nurse]:
        """
        Retrieves a paginated list of all nurse records.

        Args:
            skip (int): The number of records to skip.
            limit (int): The maximum number of records to return.

        Returns:
            List[models.Nurse]: A list of Nurse objects.
        """
        statement = select(models.Nurse).offset(skip).limit(limit)
        return self.db.execute(statement).scalars().all()

    def delete(self, *, nurse_id: uuid.UUID) -> Optional[models.Nurse]:
        """
        Deletes a nurse record from the database.
        Note: In a real application, this would likely be a soft delete
        handled by deactivating the associated User account in the service layer.

        Args:
            nurse_id (uuid.UUID): The ID of the nurse to delete.

        Returns:
            Optional[models.Nurse]: The deleted Nurse object, or None if not found.
        """
        db_nurse = self.get_by_id(nurse_id=nurse_id)
        if not db_nurse:
            return None
            
        self.db.delete(db_nurse)
        self.db.commit()
        return db_nurse
