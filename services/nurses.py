# /services/nurses.py

import uuid
from typing import Optional, Dict, Any
from fastapi import UploadFile
import shutil # Used for file operations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from typing import List

# Import necessary components
from repositories.nurses import NurseRepository
from repositories.address import AddressRepository
from repositories.nurse_documents import NurseDocumentRepository # Import the new repository
from services.users import UserService
from services.address import AddressService
import models
from schemas.nurses import NurseCreate
from schemas.address import AddressCreate as AddressCreateSchema
from schemas.nurse_documents import NurseDocumentCreate # Import the new schema
from config.security import create_access_token, create_refresh_token


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

    def create_nurse_and_user_account(
        self,
        nurse_in: NurseCreate
    ) -> models.Nurse:
        """
        Handles the initial registration of a new nurse.
        Creates the user and profile with a default unverified status.
        """
        nurse_data_dict = nurse_in.model_dump(exclude={"password", "email", "address"})
        address_data = nurse_in.address

        try:
            # Step 1: Check for existing license number or email
            if self.nurse_repo.get_by_license_number(license_number=nurse_in.license_number):
                raise ValueError(f"License number '{nurse_in.license_number}' is already registered.")
            
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
            
            self.db.refresh(new_nurse)
            token_data = {
                "id": str(new_user.id)
            }
            
            access_token = create_access_token(data=token_data)
            refresh_token = create_refresh_token(data=token_data)
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "nurse": new_nurse
            }

        except ValueError as e:
            self.db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
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


    def get_nurse_profile(self, nurse_id: uuid.UUID) -> models.Nurse:
        """
        Retrieves a nurse's profile by their ID.
        """
        nurse = self.nurse_repo.get_by_id(nurse_id=nurse_id)
        if not nurse:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nurse not found."
            )
        return nurse

    def update_nurse_profile(
        self, nurse_id: uuid.UUID, updates: Dict[str, Any]
    ) -> models.Nurse:
        """
        Updates a nurse's profile information.
        """
        nurse = self.get_nurse_profile(nurse_id)
        
        if 'license_number' in updates and nurse.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot change the license number of a verified nurse."
            )

        updated_nurse = self.nurse_repo.update(nurse_id=nurse.id, updates=updates)
        return updated_nurse

    def deactivate_nurse_account(self, nurse_id: uuid.UUID) -> bool:
        """
        Deactivates a nurse's account (soft delete).
        """
        self.get_nurse_profile(nurse_id)
        return self.user_service.deactivate_user(user_id=nurse_id)

    def verify_nurse_account(self, nurse_id: uuid.UUID) -> models.Nurse:
        """
        Verifies a nurse's account.
        """
        nurse = self.get_nurse_profile(nurse_id)
        if nurse.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nurse account is already verified."
            )
        return self.nurse_repo.update(nurse_id=nurse.id, updates={"is_verified": True})
    
    def get_nurses_by_distance(self,patient:models.Patient,radius:int=8000,skip:int=0,limit:int=100)->List[models.Nurse]:
        if(patient.primary_address is None):
            raise ValueError("Patient doesnt have a primary address!")
        nearby_nurses = self.nurse_repo.get_by_distance(patient=patient,radius=radius,skip=skip,limit=limit)
        return nearby_nurses
    