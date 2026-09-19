# /views/nurses.py

import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form

# Import dependencies, services, models, and schemas
from config.database import get_db
from utils.roleChecker import RoleChecker
from utils.logger import logger
from services.nurses import NurseService
import models
from schemas.nurses import *
from schemas.nurse_associated_services import NurseAssociatedServicesResponse
from schemas.nurse_documents import *
from services.nurse_associated_services import NurseAssociatedServiceService

# Create API router
router = APIRouter(
    prefix="/nurses",
    tags=["Nurses"]
)

# Dependency to provide the NurseService
def get_nurse_service(db=Depends(get_db)) -> NurseService:
    return NurseService(db)

def get_nurse_service_associate(db=Depends(get_db)) -> NurseAssociatedServiceService:
    return NurseAssociatedServiceService(db)


# Define role-based access dependencies
nurse_dependency = Depends(RoleChecker(allowed_roles=["Admin", "Nurse"]))
admin_dependency = Depends(RoleChecker(allowed_roles=["Admin"]))


@router.post(
    "/register",
    response_model=NurseCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new nurse"
)
async def register_new_nurse(
    nurse_in: NurseCreate,
    service: NurseService = Depends(get_nurse_service)
):
    """
    Handles the public registration of a new nurse.
    Creates a User and Nurse profile with an unverified status.
    """
    try:
        created_nurse = service.create_nurse_and_user_account(nurse_in=nurse_in)
        
        return created_nurse
    
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error during nurse registration")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during registration."
        )

@router.post(
    "/{nurse_id}/documents",
    response_model=NurseDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a verification document for a nurse"
)
def upload_nurse_document(
    nurse_id: uuid.UUID,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    service: NurseService = Depends(get_nurse_service),
    # You can add authorization here, e.g., only the nurse herself or an admin can upload
    # current_user: models.User = nurse_dependency 
):
    """
    Uploads a document (Aadhar, PAN, License) for a specific nurse.
    """
    # Basic validation for allowed document types
    allowed_types = ["Aadhar", "PAN", "NursingLicense"]
    if document_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document type. Allowed types are: {', '.join(allowed_types)}"
        )

    try:
        return service.upload_document_for_nurse(
            nurse_id=nurse_id,
            document_type=document_type,
            file=file
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error uploading document for nurse %s", nurse_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during document upload."
        )


@router.get("/me", 
            response_model=NurseAssociatedServicesResponse, 
            summary="Get current nurse's profile",
            status_code=status.HTTP_200_OK)
def get_my_profile(
    current_user: models.User = nurse_dependency,
    service: NurseService = Depends(get_nurse_service)
):
    """
    Retrieves the profile for the currently authenticated nurse.
    """
    try:
        nurse_profile = service.get_nurse_profile(nurse_id=current_user.id)
        if not nurse_profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nurse profile not found.")
        return nurse_profile
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error fetching profile for nurse %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching profile."
        )


@router.put("/me", 
            response_model=NurseAssociatedServicesResponse, 
            summary="Update current nurse's profile",
            status_code=status.HTTP_200_OK)
def update_my_profile(
    nurse_update_data: NurseUpdate,
    current_user: models.User = nurse_dependency,
    service: NurseService = Depends(get_nurse_service)
):
    """
    Updates the profile for the currently authenticated nurse.
    """
    try:
        update_dict = nurse_update_data.model_dump(exclude_unset=True)
        if not update_dict:
            raise HTTPException(status_code=400, detail="No update data provided.")

        return service.update_nurse_profile(nurse_id=current_user.id, updates=update_dict)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error updating profile for nurse %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating profile."
        )


@router.get("/all", 
            response_model=List[NurseResponse], 
            summary="Get all nurses (Admin Access)",
            dependencies=[admin_dependency],
            status_code=status.HTTP_200_OK)
def get_all_nurses(
    service: NurseService = Depends(get_nurse_service),
):
    """
    Retrieves all nurses' profiles. Requires 'Admin' role.
    """
    try:
        # Assumes a 'list_all' method exists in your NurseRepository
        return service.nurse_repo.list_all()
    except Exception:
        logger.exception("Error fetching all nurses")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching all nurses."
        )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT, summary="Deactivate current nurse's account")
def deactivate_my_account(
    current_user: models.User = nurse_dependency,
    service: NurseService = Depends(get_nurse_service)
):
    """
    Deactivates the account for the currently authenticated nurse.
    """
    try:
        service.deactivate_nurse_account(nurse_id=current_user.id)
        return None
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error deactivating account for nurse %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deactivating account."
        )


@router.get(
    "/one/{nurse_id}",
    response_model=NurseAssociatedServicesResponse,
    summary="Get nurse profile by ID (Admin Access)",
    dependencies=[admin_dependency],
    status_code=status.HTTP_200_OK
)
def get_nurse_by_id_as_admin(
    nurse_id: uuid.UUID,
    service: NurseService = Depends(get_nurse_service)
):
    """
    Retrieves a specific nurse's profile by their ID. Requires 'Admin' role.
    """
    try:
        nurse_profile = service.get_nurse_profile(nurse_id=nurse_id)
        if not nurse_profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nurse not found.")
        return nurse_profile
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error fetching nurse profile for ID %s", nurse_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching nurse profile."
        )

@router.patch(
    "/{nurse_id}/verify",
    response_model=NurseAssociatedServicesResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify a nurse's account",
    dependencies=[admin_dependency]
)
def verify_nurse_account(
    nurse_id: uuid.UUID,
    service: NurseService = Depends(get_nurse_service)
):
    """
    Verifies a nurse's account. Requires 'Admin' role.
    """
    try:
        verified_nurse = service.verify_nurse_account(nurse_id=nurse_id)
        return verified_nurse
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error verifying nurse account %s", nurse_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while verifying nurse account."
        )

