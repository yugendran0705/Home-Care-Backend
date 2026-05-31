# /services/patients.py

import uuid
from typing import Optional, Dict, Any
import json
import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

# Import necessary models, repositories, and other services
import models
from repositories.patients import PatientRepository
from .users import UserService
from .address import AddressService
from schemas.address import AddressCreate
from schemas.patients import PatientResponse
from config.security import create_access_token, create_refresh_token
from utils.redis import get_cache, set_cache, delete_cache, PATIENT_CACHE_TTL

logger = logging.getLogger(__name__)


class PatientService:
    """
    Service layer for handling all business logic related to Patients.
    It orchestrates user creation, patient profile creation, and address management.
    """

    def __init__(self, db: Session):
        """
        Initializes the service with a shared database session to ensure
        transactional integrity across different repositories and services.
        """
        self.db = db
        self.patient_repo = PatientRepository(db)
        self.user_service = UserService(db)
        # The AddressService is initialized with the same db session
        self.address_service = AddressService(db)

    def create_patient_and_user_account(
        self,
        patient_data: Dict[str, Any],
        address_data: Optional[Dict[str, Any]] = None
    ) -> models.Patient:
        """
        Handles the complete registration process for a new patient.

        This is a transactional operation that:
        1. Creates a new User account.
        2. Creates a corresponding Patient profile.
        3. Optionally, creates a primary address for the patient.

        Args:
            patient_data (Dict[str, Any]): A dictionary containing patient and user info
                                           (e.g., email, password, first_name, phone_number).
            address_data (Optional[Dict[str, Any]]): Optional dictionary with address details.

        Raises:
            HTTPException: If the email is already registered or an error occurs.

        Returns:
            models.Patient: The fully created Patient ORM object with user and address info.
        """
        # Extract user credentials from the input data
        email = patient_data.get("email")
        password = patient_data.get("password")

        if not email or not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email and password are required to create an account."
            )

        # Start a transaction block
        try:
            # Step 1: Create the User account using the UserService
            new_user = self.user_service.create_new_user(
                email=email,
                password=password,
                user_type="Patient"  # Ensure the user_type is 'Patient'
            )

            # Step 2: Create the Patient profile linked to the new user ID
            patient_profile_data = {
                "id": new_user.id,
                "first_name": patient_data.get("first_name"),
                "last_name": patient_data.get("last_name"),
                "phone_number": patient_data.get("phone_number"),
                "date_of_birth": patient_data.get("date_of_birth"),
                "gender": patient_data.get("gender"),
            }
            new_patient = self.patient_repo.create(patient_profile_data)

            # Step 3 (Optional): Create the address for the user
            if address_data:
                address_schema = AddressCreate(**address_data)
                self.address_service.create_address_for_user(
                    address_in=address_schema,
                    user_id=new_user.id
                )
            
            # Reload patient with relationships to ensure they're eagerly loaded
            new_patient = self.patient_repo.get_by_id(new_user.id)
            token_data = {
                "id": str(new_user.id)
            }
            
            access_token = create_access_token(data=token_data)
            refresh_token = create_refresh_token(data=token_data)
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "patient": new_patient
            }

        except ValueError as e:
            # This catches the "Email already registered" error from UserService
            self.db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        except Exception as e:
            # Rollback in case of any other error during patient/address creation
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred: {e}",
            )

    def get_patient_profile(self, patient_id: uuid.UUID) -> PatientResponse:
        """
        Args:
            patient_id (uuid.UUID): The unique ID of the patient (same as user_id).

        Raises:
            HTTPException: 404 Not Found, if the patient does not exist.

        Returns:
            PatientResponse: Patient data as a Pydantic model
        """
        # Use user_id for cache key (patient_id == user_id)
        cache_key = f"user_{patient_id}"
        
        # Try to get from cache
        cached_data = get_cache(cache_key)
        if cached_data:
            try:
                # Deserialize JSON to dict and create Pydantic model
                patient_dict = json.loads(cached_data.decode('utf-8'))
                patient_response = PatientResponse(**patient_dict)
                logger.debug(f"Cache hit for user {patient_id}")
                return patient_response
            except Exception as e:
                # Corrupted cache data - log and fall through to DB
                logger.warning(f"Failed to deserialize cached patient for user {patient_id}: {e}")
        
        # Cache miss or unavailable - fetch from database
        logger.debug(f"Fetching patient for user {patient_id} from database")
        patient = self.patient_repo.get_by_id(patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found."
            )
        
        # Convert to Pydantic model
        patient_response = PatientResponse.model_validate(patient, from_attributes=True)
        
        # Cache the result
        try:
            # Cache as JSON with TTL (15 min default) to prevent indefinite stale data
            cached_json = json.dumps(patient_response.model_dump(mode='json')).encode('utf-8')
            if set_cache(cache_key, cached_json, ex=PATIENT_CACHE_TTL):
                logger.debug(f"Cached patient for user {patient_id} as JSON with {PATIENT_CACHE_TTL}s TTL")
        except Exception as e:
            # Caching failed - log but continue with response
            logger.warning(f"Failed to cache patient for user {patient_id}: {e}")
        
        return patient_response

    def update_patient_profile(
        self, patient_id: uuid.UUID, updates: Dict[str, Any]
    ) -> models.Patient:
        """
        Updates a patient's profile information. Delegates updates to the
        UserService for user-specific fields (like email) and handles
        patient-specific fields directly.

        Args:
            patient_id (uuid.UUID): The ID of the patient to update.
            updates (Dict[str, Any]): A dictionary of fields to update.

        Returns:
            models.Patient: The updated Patient ORM object.
        """
        # Fetch patient directly from DB (need ORM object for repository updates)
        patient = self.patient_repo.get_by_id(patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found."
            )

        # Separate updates for the User and Patient models
        user_update_data = {}
        patient_update_data = {}

        # Define which keys belong to which model
        user_keys = {'email', 'password'}
        patient_keys = {'first_name', 'last_name', 'phone_number', 'date_of_birth', 'gender'}

        for key, value in updates.items():
            if key in user_keys:
                user_update_data[key] = value
            elif key in patient_keys:
                patient_update_data[key] = value

        try:
            # Delegate user-related updates to the UserService
            if user_update_data:
                self.user_service.update_user_profile(user_id=patient_id, updates=user_update_data)

            # Handle patient-specific updates via the PatientRepository
            if patient_update_data:
                self.patient_repo.update(patient=patient, updates=patient_update_data)

        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

        # Invalidate cache and reload patient with relationships
        delete_cache(f"user_{patient_id}")
        
        patient = self.patient_repo.get_by_id(patient_id)
        return patient

    def deactivate_patient_account(self, patient_id: uuid.UUID) -> bool:
        """
        Deactivates a patient's account. This is a soft delete.

        Args:
            patient_id (uuid.UUID): The ID of the patient to deactivate.

        Returns:
            bool: True if the deactivation was successful.
        """
        # Verify patient exists (raises 404 if not)
        patient = self.patient_repo.get_by_id(patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found."
            )
        
        # Use the user service to handle deactivation logic
        result = self.user_service.deactivate_user(patient_id)
        if result:
            delete_cache(f"user_{patient_id}")
        return result
    
    def get_all_patients(self, skip: int = 0, limit: int = 100) -> list[models.Patient]:
        """
        Retrieves all patients with optional pagination.

        Args:
            skip (int): Number of records to skip (for pagination).
            limit (int): Maximum number of records to return.

        Returns:
            list[models.Patient]: A list of Patient ORM objects.
        """
        return self.patient_repo.get_all(skip=skip, limit=limit)    
        