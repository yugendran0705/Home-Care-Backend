# /services/nurse_services.py

import uuid
from typing import List, Optional
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

# Import necessary components
from repositories.nurse_services import NurseServiceRepository
from repositories.nurses import NurseRepository
from repositories.services import ServiceRepository
import models
from schemas.nurse_services import NurseServiceCreate, NurseServiceResponse


class NurseServiceService:
    """
    Service layer for handling all business logic related to Nurse-Service associations.
    """

    def __init__(self, db: Session):
        """
        Initializes the service with a shared database session.
        """
        self.db = db
        self.nurse_service_repo = NurseServiceRepository(db)
        self.nurse_repo = NurseRepository(db)
        self.service_repo = ServiceRepository(db)

    def assign_service_to_nurse(self, nurse_service_in: NurseServiceCreate) -> models.NurseService:
        """
        Assigns a service to a nurse with validation.

        Args:
            nurse_service_in (NurseServiceCreate): The service assignment data.

        Returns:
            models.NurseService: The created association.

        Raises:
            HTTPException: If validation fails.
        """
        nurse_id = nurse_service_in.nurse_id
        service_id = nurse_service_in.service_id

        # Validate that nurse exists
        nurse = self.nurse_repo.get_by_id(nurse_id=nurse_id)
        if not nurse:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nurse with ID {nurse_id} not found."
            )

        # Validate that service exists
        service = self.service_repo.get_by_id(service_id=service_id)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service with ID {service_id} not found."
            )

        # Check if the service is already assigned to this nurse
        existing = self.nurse_service_repo.get_specific_nurse_service(
            nurse_id=nurse_id, service_id=service_id
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Service {service_id} is already assigned to nurse {nurse_id}."
            )

        # Create the association
        return self.nurse_service_repo.add_service_to_nurse(nurse_service_in=nurse_service_in)

    def get_services_for_nurse(self, nurse_id: uuid.UUID) -> List[NurseServiceResponse]:
        """
        Retrieves all services offered by a specific nurse.

        Args:
            nurse_id (uuid.UUID): The nurse's ID.

        Returns:
            List[NurseServiceResponse]: List of nurse-service associations.

        Raises:
            HTTPException: If nurse not found.
        """
        # Validate that nurse exists
        nurse = self.nurse_repo.get_by_id(nurse_id=nurse_id)
        if not nurse:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nurse with ID {nurse_id} not found."
            )

        nurse_services = self.nurse_service_repo.get_services_for_nurse(nurse_id=nurse_id)
        return [NurseServiceResponse.model_validate(ns) for ns in nurse_services]

    def update_service_price(self, nurse_id: uuid.UUID, service_id: uuid.UUID, new_price: Decimal) -> models.NurseService:
        """
        Updates the price for an existing nurse-service link.

        Args:
            nurse_id (uuid.UUID): The nurse's ID.
            service_id (uuid.UUID): The service's ID.
            new_price (Decimal): The new price.

        Returns:
            models.NurseService: The updated association.

        Raises:
            HTTPException: If validation fails.
        """
        # Validate that nurse exists
        nurse = self.nurse_repo.get_by_id(nurse_id=nurse_id)
        if not nurse:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nurse with ID {nurse_id} not found."
            )

        # Validate that service exists
        service = self.service_repo.get_by_id(service_id=service_id)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service with ID {service_id} not found."
            )

        # Check if the association exists
        existing = self.nurse_service_repo.get_specific_nurse_service(
            nurse_id=nurse_id, service_id=service_id
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service {service_id} is not assigned to nurse {nurse_id}."
            )

        # Update the price
        updated = self.nurse_service_repo.update_price(
            nurse_id=nurse_id, service_id=service_id, new_price=new_price
        )
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update price."
            )
        return updated

    def remove_service_from_nurse(self, nurse_id: uuid.UUID, current_user_id: uuid.UUID) -> int:
        """
        Removes all services from a nurse's profile.
        
        Args:
            nurse_id (uuid.UUID): The nurse's ID.
            current_user_id (uuid.UUID): The ID of the currently authenticated user.

        Returns:
            int: The number of services removed.

        Raises:
            HTTPException: If validation fails.
        """
        # Validate that current user is the nurse or is an admin
        current_user = self.nurse_repo.db.query(models.User).filter(models.User.id == current_user_id).first()
        if current_user and current_user.user_type == "Nurse" and nurse_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Nurses can only remove their own services."
            )
        # Admins can remove services from any nurse

        # Validate that nurse exists
        nurse = self.nurse_repo.get_by_id(nurse_id=nurse_id)
        if not nurse:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nurse with ID {nurse_id} not found."
            )

        # Check if nurse has any services
        nurse_services = self.nurse_service_repo.get_services_for_nurse(nurse_id=nurse_id)
        if not nurse_services:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nurse {nurse_id} has no services to remove."
            )

        # Remove all services
        count = self.nurse_service_repo.remove_all_services_from_nurse(nurse_id=nurse_id)
        return count