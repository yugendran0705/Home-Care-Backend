
# /services/services.py

import uuid
from typing import List, Optional, Dict, Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from repositories.nursing_services import NursingServiceRepository
import models
from schemas.nursing_services import NursingServiceCreate, NursingServiceUpdate


class NursingServiceService:
    """
    Service layer for handling business logic related to services offered.
    """

    def __init__(self, db: Session):
        """
        Initializes the service with a database session.

        Args:
            db (Session): The SQLAlchemy database session.
        """
        self.db = db
        self.service_repo = NursingServiceRepository(db)

    def create_service(self, *, service_in: NursingServiceCreate) -> models.NursingService:
        """
        Creates a new service.

        Args:
            service_in (ServiceCreate): The data for the new service.

        Returns:
            models.Service: The newly created service object.

        Raises:
            HTTPException: If a service with the same name already exists.
        """
        # Check if a service with the same name already exists
        existing_service = self.service_repo.get_by_name(service_name=service_in.service_name)
        if existing_service:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A service with the name '{service_in.service_name}' already exists.",
            )

        try:
            new_service = self.service_repo.create(service_in=service_in)
            return new_service
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred: {e}",
            )

    def get_service_by_id(self, *, service_id: uuid.UUID) -> models.NursingService:
        """
        Retrieves a service by its ID.

        Args:
            service_id (uuid.UUID): The ID of the service to retrieve.

        Returns:
            models.Service: The service object.

        Raises:
            HTTPException: If the service is not found.
        """
        service = self.service_repo.get_by_id(service_id=service_id)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service not found.",
            )
        return service

    def update_service(
        self, *, service_id: uuid.UUID, updates: NursingServiceUpdate
    ) -> models.NursingService:
        """
        Updates an existing service.

        Args:
            service_id (uuid.UUID): The ID of the service to update.
            updates (ServiceUpdate): The data to update.

        Returns:
            models.Service: The updated service object.
        """
        # First, ensure the service exists
        self.get_service_by_id(service_id=service_id)

        # Exclude unset fields from the update data
        update_data = updates.model_dump(exclude_unset=True)

        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No update data provided.",
            )

        updated_service = self.service_repo.update(service_id=service_id, updates=update_data)
        return updated_service

    def list_all_services(self, *, skip: int = 0, limit: int = 100) -> List[models.NursingService]:
        """
        Retrieves a list of all available services.

        Args:
            skip (int): Number of records to skip for pagination.
            limit (int): Maximum number of records to return.

        Returns:
            List[models.Service]: A list of service objects.
        """
        return self.service_repo.list_all(skip=skip, limit=limit)

    def delete_service(self, *, service_id: uuid.UUID) -> Dict[str, str]:
        """
        Deletes a service. In a real-world application, this should
        likely be a "soft delete" (e.g., setting `is_active` to False).

        Args:
            service_id (uuid.UUID): The ID of the service to delete.

        Returns:
            Dict[str, str]: A confirmation message.
        """
        # Ensure the service exists before trying to delete
        self.get_service_by_id(service_id=service_id)

        deleted_service = self.service_repo.delete(service_id=service_id)
        if not deleted_service:
            # This case should ideally not be hit due to the check above, but it's good practice
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service not found.",
            )
            
        return {"message": f"Service with ID {service_id} has been deleted."}

