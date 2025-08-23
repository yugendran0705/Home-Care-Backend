# /services/patients.py

import uuid
from typing import Optional, Dict, Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

# Import necessary models, repositories, and other services
import models
from repositories.patients import PatientRepository
from repositories.address import AddressRepository
from .users import UserService
from .address import AddressService
from schemas.address import AddressCreate


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
        # The AddressService requires an AddressRepository, so we instantiate it here
        self.address_service = AddressService(AddressRepository(db))

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

            # Step 3 (Optional): Create and link the primary address
            if address_data:
                address_schema = AddressCreate(**address_data)
                new_address = self.address_service.create_address_for_user(
                    address_in=address_schema,
                    user_id=new_user.id
                )
                # Set the created address as the patient's primary address
                new_patient = self.patient_repo.update(
                    patient=new_patient,
                    updates={"address_id": new_address.id, "is_primary": True}
                )
            
            self.db.refresh(new_patient)
            return new_patient

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

    def get_patient_profile(self, patient_id: uuid.UUID) -> models.Patient:
        """
        Retrieves a complete patient profile by their ID.

        Args:
            patient_id (uuid.UUID): The unique ID of the patient.

        Raises:
            HTTPException: 404 Not Found, if the patient does not exist.

        Returns:
            models.Patient: The Patient ORM object, with related user/address data loaded.
        """
        patient = self.patient_repo.get_by_id(patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found."
            )
        return patient

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
        patient = self.get_patient_profile(patient_id)

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

        self.db.refresh(patient)
        return patient

    def deactivate_patient_account(self, patient_id: uuid.UUID) -> bool:
        """
        Deactivates a patient's account. This is a soft delete.

        Args:
            patient_id (uuid.UUID): The ID of the patient to deactivate.

        Returns:
            bool: True if the deactivation was successful.
        """
        # get_patient_profile will raise 404 if not found
        self.get_patient_profile(patient_id)
        
        # Use the user service to handle deactivation logic
        return self.user_service.deactivate_user(patient_id)
    
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
        