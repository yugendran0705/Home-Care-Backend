# /repositories/nursing_services.py

import uuid
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import select
import models
from schemas.nursing_services import NursingServiceCreate  # Assumes you will create this schema


class NursingServiceRepository:
    """
    Repository for handling all direct database operations for the Service model.
    """

    def __init__(self, db: Session):
        """
        Initializes the repository with a database session.

        Args:
            db (Session): The SQLAlchemy database session.
        """
        self.db = db

    def create(self, *, service_in: NursingServiceCreate) -> models.NursingService:
        """
        Creates a new service that can be offered by nurses.

        Args:
            service_in (ServiceCreate): A Pydantic schema with the new service data.

        Returns:
            models.NursingService: The newly created NursingService ORM object.
        """
        db_service = models.NursingService(**service_in.model_dump())

        self.db.add(db_service)
        self.db.commit()
        self.db.refresh(db_service)
        return db_service

    def get_by_id(self, *, service_id: uuid.UUID) -> Optional[models.NursingService]:
        """
        Retrieves a service by its primary key.

        Args:
            service_id (uuid.UUID): The ID of the service to retrieve.

        Returns:
            Optional[models.NursingService]: The NursingService object if found, otherwise None.
        """
        return self.db.get(models.NursingService, service_id)

    def get_by_name(self, *, service_name: str) -> Optional[models.NursingService]:
        """
        Retrieves a service by its unique name.

        Args:
            service_name (str): The name of the service.

        Returns:
            Optional[models.NursingService]: The NursingService object if found, otherwise None.
        """
        statement = select(models.NursingService).where(
            models.NursingService.service_name == service_name
        )
        return self.db.execute(statement).scalar_one_or_none()

    def update(
        self, *, service_id: uuid.UUID, updates: Dict[str, Any]
    ) -> Optional[models.NursingService]:
        """
        Updates an existing service's details.

        Args:
            service_id (uuid.UUID): The ID of the service to update.
            updates (Dict[str, Any]): A dictionary of fields to update.

        Returns:
            Optional[models.NursingService]: The updated NursingService object, or None if not found.
        """
        db_service = self.get_by_id(service_id=service_id)
        if not db_service:
            return None

        for key, value in updates.items():
            setattr(db_service, key, value)

        self.db.add(db_service)
        self.db.commit()
        self.db.refresh(db_service)
        return db_service

    def list_all(self, *, skip: int = 0, limit: int = 100) -> List[models.NursingService]:
        """
        Retrieves a paginated list of all services.

        Args:
            skip (int): The number of records to skip.
            limit (int): The maximum number of records to return.

        Returns:
            List[models.NursingService]: A list of NursingService objects.
        """
        statement = select(models.NursingService).offset(skip).limit(limit)
        return self.db.execute(statement).scalars().all()

    def delete(self, *, service_id: uuid.UUID) -> Optional[models.NursingService]:
        """
        Deletes a service from the database.
        Note: A soft delete (setting `is_active` to False) is often preferred
        and would typically be handled in the service layer.

        Args:
            service_id (uuid.UUID): The ID of the service to delete.

        Returns:
            Optional[models.NursingService]: The deleted NursingService object, or None if not found.
        """
        db_service = self.get_by_id(service_id=service_id)
        if not db_service:
            return None

        self.db.delete(db_service)
        self.db.commit()
        return db_service
