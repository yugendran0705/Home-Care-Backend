
# /services/services.py
# adding in comments for personal notes
import uuid
import json #converting str to dicts and vice versa
import logging #linking to central logging pipeline
from typing import List, Optional, Dict, Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from repositories.services import ServiceRepository
import models
from schemas.services import ServiceCreate, ServiceUpdate, ServiceResponse  

from utils.redis import get_cache, set_cache, delete_cache, SERVICE_CACHE_TTL
logger = logging.getLogger(__name__) #logging
CACHE_KEY_PREFIX = "service:profile:" #service prefix string defn

class ServiceService:
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
        self.service_repo = ServiceRepository(db)

    def create_service(self, *, service_in: ServiceCreate) -> models.Service:
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

    def get_service_by_id(self, *, service_id: uuid.UUID) -> ServiceResponse:
        """
        Retrieves a service by its ID, checks redis cache first

        """
        cache_key = f"{CACHE_KEY_PREFIX}{service_id}"

        #lookup index key in redis ram
        cached_data = get_cache(cache_key)
        if cached_data:
            try:
                service_dict = json.loads(cached_data.decode('utf-8'))
                service_response = ServiceResponse(**service_dict)
                logger.debug(f"Cache hit for service {service_id}")
                return service_response
            except Exception as e:
                logger.warning(f"Failed to deserialize cached service for ID {service_id}: {e}")

        #cache missed, fallback to pg db query
        logger.debug(f"Fetching service for ID {service_id} from database")
        service = self.service_repo.get_by_id(service_id=service_id)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service not found.",
            )

        # 3. sqlalchemy db obj to pydantic model
        service_response = ServiceResponse.model_validate(service, from_attributes=True)
        
        # 4. save data into redis, fast retrieval 
        try:
            cached_json = json.dumps(service_response.model_dump(mode='json')).encode('utf-8')
            if set_cache(cache_key, cached_json, ex=SERVICE_CACHE_TTL):
                logger.debug(f"Cached service {service_id} as JSON with {SERVICE_CACHE_TTL}s TTL")
        except Exception as e:
            logger.warning(f"Failed to cache service {service_id}: {e}")
            
        return service_response

    def update_service(
            self, *, service_id: uuid.UUID, updates: ServiceUpdate
        ) -> models.Service:
            """
            Updates an existing service and invalidates its cache.
            """
            # fetch directly from db to editable orm obj
            service = self.service_repo.get_by_id(service_id=service_id)
            if not service:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Service not found.",
                )
            update_data = updates.model_dump(exclude_unset=True)
            if not update_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No update data provided.",
                )

            # data update in sql
            updated_service = self.service_repo.update(service_id=service_id, updates=update_data)

            #clear stale, out of date cache  out of redis ram
            delete_cache(f"{CACHE_KEY_PREFIX}{service_id}")

            return updated_service

    def list_all_services(self, *, skip: int = 0, limit: int = 100) -> List[models.Service]:
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
        Deletes a service and completely clears its cache instance.
        """
        # check directly from db to prevent stale
        service = self.service_repo.get_by_id(service_id=service_id)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service not found.",
            )

        deleted_service = self.service_repo.delete(service_id=service_id)
        if not deleted_service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service not found.",
            )
            
        # Clear the cache index so no ghost records remain in RAM memory
        delete_cache(f"{CACHE_KEY_PREFIX}{service_id}")

        return {"message": f"Service with ID {service_id} has been deleted."}