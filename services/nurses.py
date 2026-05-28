# /services/nurses.py

import uuid
import json
from typing import Dict, Any
from fastapi import UploadFile
import shutil # Used for file operations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

# Import necessary components
from repositories.nurses import NurseRepository
from repositories.nurse_associated_services import NurseAssociatedServiceRepository
from repositories.nurse_documents import NurseDocumentRepository # Import the new repository
from repositories.nursing_services import NursingServiceRepository  # <- for validating service IDs during registration
from services.users import UserService
from services.address import AddressService
import models
from schemas.nurses import NurseCreate, NurseCreateResponse, NurseResponse
from schemas.address import AddressCreate as AddressCreateSchema
from schemas.nurse_documents import NurseDocumentCreate # Import the new schema
from schemas.nurse_associated_services import NurseAssociatedServicesResponse
from schemas.nursing_services import NursingServiceResponse
from config.security import create_access_token, create_refresh_token

import logging
logger = logging.getLogger(__name__)

from utils.redis import get_cache, set_cache, delete_cache, NURSE_CACHE_TTL



class NurseService:
    """
    Service layer for handling all business logic related to Nurses.
    """

    def __init__(self, db: Session):
        """
        Initializes the service with a shared database session.
        """
        self.db = db
        self.nurse_repo = NurseRepository(db)
        self.user_service = UserService(db)
        self.address_service = AddressService(db)
        self.doc_repo = NurseDocumentRepository(db) # Initialize the document repository
        self.nurse_service_repo = NurseAssociatedServiceRepository(db)
        self.service_repo = NursingServiceRepository(db)  # used for service existence checks

    def create_nurse_and_user_account(
        self,
        nurse_in: NurseCreate
    ) -> NurseCreateResponse:
        """
        Handles the initial registration of a new nurse.
        Creates the user and profile with a default unverified status.
        Also links any services provided during registration.
        """
        nurse_data_dict = nurse_in.model_dump(exclude={"password", "email", "address", "services"})
        address_data = nurse_in.address
        services_data = nurse_in.services

        # Step 0: Validate any provided services IDs before doing any writes.
        service_ids = []
        if services_data:
            for service in services_data:
                if not service.service_ids:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Each service registration item must include at least one service_id."
                    )

                for service_id_raw in service.service_ids:
                    try:
                        service_id = uuid.UUID(str(service_id_raw))
                    except Exception:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Invalid service_id format: {service_id_raw}"
                        )

                    if service_id in service_ids:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Duplicate service_id detected: {service_id}"
                        )

                    service = self.service_repo.get_by_id(service_id=service_id)
                    if not service:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Service with ID {service_id} not found."
                        )

                    if not service.is_active:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Service with ID {service_id} is not active and cannot be assigned."
                        )

                    service_ids.append(service_id)

        try:
            # Step 1: Check for existing license number or email
            if self.nurse_repo.get_by_license_number(license_number=nurse_in.license_number):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"License number '{nurse_in.license_number}' is already registered."
                )
            
            # Step 2: Create the User account
            new_user = self.user_service.create_new_user(
                email=nurse_in.email,
                password=nurse_in.password,
                user_type="Nurse"
            )

            # Step 3: Create the Nurse profile with is_verified=False by default
            nurse_profile_data = {
                "id": new_user.id,
                "is_verified": False, # Nurse is NOT verified on creation
                **nurse_data_dict
            }
            new_nurse = self.nurse_repo.create(nurse_data=nurse_profile_data)

            # Step 4 (Optional): Create and link the primary address
            if address_data:
                address_schema = AddressCreateSchema(**address_data.model_dump())
                new_address = self.address_service.create_address_for_user(
                    address_in=address_schema,
                    user_id=new_user.id
                )
                new_nurse = self.nurse_repo.update(
                    nurse_id=new_nurse.id,
                    updates={"address_id": new_address.id}
                )
            
            # Step 5 (Optional): Bulk create and link services
            if service_ids:
                self.nurse_service_repo.bulk_create_for_nurse(
                    nurse_id=new_nurse.id,
                    service_ids=service_ids
                )
            
            self.db.refresh(new_nurse)
            
            token_data = {
                "id": str(new_user.id)
            }

            access_token = create_access_token(data=token_data)
            refresh_token = create_refresh_token(data=token_data)
            
            return NurseCreateResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                nurse=NurseResponse.model_validate(new_nurse),
                services=[NursingServiceResponse.model_validate(self.service_repo.get_by_id(service_id=sid)) for sid in service_ids] if service_ids else []
            )

        
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred during registration: {e}",
            )

    def upload_document_for_nurse(
        self, *, nurse_id: uuid.UUID, document_type: str, file: UploadFile
    ) -> models.NurseDocument:
        """
        Handles uploading a document, saving it, and creating a DB record.
        """
        # Ensure the nurse exists
        self.get_nurse_profile(nurse_id=nurse_id)

        # --- File Storage Logic ---
        # In a real application, you would upload to a cloud service like AWS S3.
        # For this example, we'll save it to a local directory named 'uploads'.
        # This is a PLACEHOLDER and should be replaced with a proper storage solution.
        file_location = f"uploads/{uuid.uuid4()}_{file.filename}"
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
        
        # The URL would be the public URL from your cloud storage service.
        # For this local example, it's just the file path.
        document_url = file_location
        # --- End of File Storage Logic ---

        try:
            doc_schema = NurseDocumentCreate(
                nurse_id=nurse_id,
                document_type=document_type,
                document_url=document_url # Use the URL of the saved file
            )
            created_document = self.doc_repo.create(document_in=doc_schema)
            return created_document
        except ValueError as e:
            # This catches the "document type already exists" error from the repository
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


    def get_nurse_profile(self, nurse_id: uuid.UUID) -> NurseAssociatedServicesResponse:
        """
        Retrieves a nurse's profile by their ID along with their services.
        """

        cache_key = f"user_{nurse_id}"

        cached_data = get_cache(cache_key)
        if cached_data:
            try:
                nurse_dict = json.loads(cached_data.decode('utf-8'))
                nurse_response = NurseAssociatedServicesResponse(**nurse_dict)
                logger.debug(f"Cache hit for user {nurse_id}")
                return nurse_response
        
            except Exception as e:
                logger.warning(f"Failed to deserialize cached nurse for user {nurse_id}: {e}")
                delete_cache(cache_key)  # Remove the corrupted cache entry

        logger.debug(f"Fetching nurse for user {nurse_id} from database")

        nurse = self.nurse_repo.get_by_id(nurse_id=nurse_id)
        if not nurse:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nurse not found."
            )
        
        nurse_services = self.nurse_service_repo.get_by_nurse(nurse_id=nurse_id)
        service_items = [NursingServiceResponse.model_validate(ns.service) for ns in nurse_services]
        # Convert to Pydantic model
        nurse_profile_response =  NurseAssociatedServicesResponse(
            nurse=NurseResponse.model_validate(nurse),
            services=service_items,
        )
        # Cache the result
        try:
            cached_json = json.dumps(nurse_profile_response.model_dump(mode = "json")).encode('utf-8')
            if set_cache(cache_key, cached_json, ex=NURSE_CACHE_TTL):
                logger.debug(f"Cached nurse profile for user {nurse_id} as json with TTL {NURSE_CACHE_TTL} seconds")
        except Exception as e:
            logger.warning(f"Failed to cache nurse profile for user {nurse_id}: {e}")


        return nurse_profile_response
        

    def update_nurse_profile(
        self, nurse_id: uuid.UUID, updates: Dict[str, Any]
    ) -> NurseAssociatedServicesResponse:
        """
        Updates a nurse's profile information.
        """
        nurse_profile = self.get_nurse_profile(nurse_id)

        updated_nurse = self.nurse_repo.update(nurse_id=nurse_profile.nurse.id, updates=updates)
        if not updated_nurse:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nurse not found."
            )

        delete_cache(f"user_{nurse_id}")
        return self.get_nurse_profile(nurse_id)

    def deactivate_nurse_account(self, nurse_id: uuid.UUID) -> bool:
        """
        Deactivates a nurse's account (soft delete).
        """
        self.get_nurse_profile(nurse_id)
        delete_cache(f"user_{nurse_id}")
        return self.user_service.deactivate_user(user_id=nurse_id)

    def verify_nurse_account(self, nurse_id: uuid.UUID) -> NurseAssociatedServicesResponse:
        """
        Verifies a nurse's account.
        """
        nurse_profile = self.get_nurse_profile(nurse_id)
        if nurse_profile.nurse.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nurse account is already verified."
            )

        updated_nurse = self.nurse_repo.update(nurse_id=nurse_id, updates={"is_verified": True})
        if not updated_nurse:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nurse not found."
            )

        delete_cache(f"user_{nurse_id}")
        return self.get_nurse_profile(nurse_id)
