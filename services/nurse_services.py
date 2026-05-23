# /services/nurse_services.py

import json
import json
import uuid
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

# Import necessary components
from repositories.nurse_services import NurseServiceRepository
from repositories.nurses import NurseRepository
from repositories.services import ServiceRepository
from schemas.nurses import NurseResponse
from schemas.nurse_services import (
    NurseServiceBulkCreate,
    NurseServicesResponse,
)
from schemas.services import ServiceResponse
from utils.redis import delete_cache

import logging
logger = logging.getLogger(__name__)

from utils.redis import get_cache, set_cache, delete_cache, NURSE_SERVICES_CACHE_TTL


class NurseAssociateService:
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

    def assign_service_to_nurse(self, nurse_id, nurse_service_in: NurseServiceBulkCreate) -> NurseServicesResponse:
        """
        Assigns multiple services to a single nurse using bulk create.

        Args:
            nurse_service_in (NurseServiceBulkCreate): The service assignment data.

        Returns:
            NurseServicesResponse: The created nurse-service assignment summary.

        Raises:
            HTTPException: If validation fails.
        """
        service_ids = nurse_service_in.service_ids or []

        if not service_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one service_id is required."
            )

        # Validate that nurse exists
        nurse = self.nurse_repo.get_by_id(nurse_id=nurse_id)
        if not nurse:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nurse with ID {nurse_id} not found."
            )

        unique_service_ids = list(dict.fromkeys(service_ids))
        if len(unique_service_ids) != len(service_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate service_ids are not allowed." 
            )

        # Validate that every service exists
        missing_services = []
        for service_id in unique_service_ids:
            if not self.service_repo.get_by_id(service_id=service_id):
                missing_services.append(service_id)

        if missing_services:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service(s) with ID(s) {missing_services} not found."
            )

        # Validate that every service is active
        inactive_services = []
        for service_id in unique_service_ids:
            service = self.service_repo.get_by_id(service_id=service_id)
            if service and not service.is_active:
                inactive_services.append(service_id)

        if inactive_services:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Service(s) with ID(s) {inactive_services} are not active and cannot be assigned."
            )

        # Ensure none of the services are already assigned to this nurse
        duplicate_assignments = []
        for service_id in unique_service_ids:
            if self.nurse_service_repo.get_one(
                nurse_id=nurse_id,
                service_id=service_id
            ):
                duplicate_assignments.append(service_id)

        if duplicate_assignments:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Service(s) {duplicate_assignments} are already assigned to nurse {nurse_id}."
            )

        result = self.nurse_service_repo.bulk_create_for_nurse(
            nurse_id=nurse_id,
            service_ids=unique_service_ids
        )

        return NurseServicesResponse(
            nurse=NurseResponse.model_validate(nurse),
            services=[ServiceResponse.model_validate(ns.service) for ns in result]
        )

    def get_services_for_nurse(self, nurse_id: uuid.UUID) -> NurseServicesResponse:
        """
        Retrieves all services offered by a specific nurse.

        Args:
            nurse_id (uuid.UUID): The nurse's ID.

        Returns:
            NurseServicesResponse: Nested nurse profile with service list.

        Raises:
            HTTPException: If nurse not found.
        """
        cache_key = f"nurse_services_{nurse_id}"

        cached_data = get_cache(cache_key)
        if cached_data:
            try:
                # Deserialize JSON to dict and create Pydantic model
                cached_dict = json.loads(cached_data.decode('utf-8'))
                cached_model = NurseServicesResponse(**cached_dict)
                logger.debug(f"Cache hit for nurse services with key {nurse_id}")
                return cached_model
            except Exception as e:
                logger.warning(f"Failed to deserialize cache for nurse {nurse_id}: {e}")
                delete_cache(cache_key)
                

        logger.debug(f"fetching nurse services from database for nurse {nurse_id}")
        # Fetch from database

        # Validate that nurse exists
        nurse = self.nurse_repo.get_by_id(nurse_id=nurse_id)
        if not nurse:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Nurse with ID {nurse_id} not found."
            )

        nurse_services = self.nurse_service_repo.get_by_nurse(nurse_id=nurse_id)
        service_items = [ServiceResponse.model_validate(ns.service) for ns in nurse_services]
        nurse_services_response =NurseServicesResponse(
            nurse=NurseResponse.model_validate(nurse),
            services=service_items,
        )
        try:
            cached_json = json.dumps(nurse_services_response.model_dump(mode='json')).encode('utf-8')
            if set_cache(cache_key, cached_json, ex=NURSE_SERVICES_CACHE_TTL):
                logger.debug(f"Cached nurse services for nurse {nurse_id} as JSON with {NURSE_SERVICES_CACHE_TTL}s TTL")
        except Exception as e:
            logger.warning(f"Failed to cache nurse services for nurse {nurse_id}: {e}")

        return nurse_services_response

    def update_services_for_nurse(self, nurse_id: uuid.UUID, service_ids: List[uuid.UUID]) -> NurseServicesResponse:
        """
        Updates the services for a nurse by replacing the old list with a new one.

        Args:
            nurse_id (uuid.UUID): The nurse's ID.
            service_ids (List[uuid.UUID]): The new list of service IDs to assign to the nurse.

        Returns:
            NurseServicesResponse: The updated nurse profile with new services.

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

        # Get unique service IDs
        unique_service_ids = list(dict.fromkeys(service_ids))
        if len(unique_service_ids) != len(service_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate service_ids are not allowed."
            )

        # Validate that every service exists
        missing_services = []
        for service_id in unique_service_ids:
            if not self.service_repo.get_by_id(service_id=service_id):
                missing_services.append(service_id)

        if missing_services:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service(s) with ID(s) {missing_services} not found."
            )

        inactive_services = []
        for service_id in unique_service_ids:
            service = self.service_repo.get_by_id(service_id=service_id)
            if service and not service.is_active:
                inactive_services.append(service_id)

        if inactive_services:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Service(s) with ID(s) {inactive_services} are not active and cannot be assigned."
            )

        # Atomically replace all services in a single transaction
        result = self.nurse_service_repo.replace_services_for_nurse(
            nurse_id=nurse_id,
            service_ids=unique_service_ids
        )
        service_items = [ServiceResponse.model_validate(ns.service) for ns in result]

<<<<<<< HEAD
        nurse_services_response = NurseServicesResponse(
=======
        delete_cache(f"user_{nurse_id}")

        return NurseServicesResponse(
>>>>>>> bc6a694 (Caching for Nurse)
            nurse=NurseResponse.model_validate(nurse),
            services=service_items,
        )

        # Invalidate cache for this nurse's services
        delete_cache(f"nurse_services_{nurse_id}")

        return nurse_services_response
    
    def remove_service_from_nurse(self, nurse_id: uuid.UUID) -> bool:
        """
        Removes all services from a nurse's profile.

        Args:
            nurse_id (uuid.UUID): The nurse's ID.

        Returns:
            bool: True if services were removed, False if no services were found for the nurse.

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

        self.nurse_service_repo.delete_all_by_nurse(nurse_id=nurse_id)
<<<<<<< HEAD
        # Invalidate cache for this nurse's services
        delete_cache(f"nurse_services_{nurse_id}")
=======
        delete_cache(f"user_{nurse_id}")
>>>>>>> bc6a694 (Caching for Nurse)
        return True
        