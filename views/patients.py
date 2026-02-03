# /views/patients.py

import uuid
from fastapi import APIRouter, Depends, HTTPException, status

# Import dependencies, services, models, and schemas
from config.database import get_db
from utils.roleChecker import RoleChecker
from services.patients import PatientService
import models
from schemas.patients import *

# Create API router
router = APIRouter(
    prefix="/patients",
    tags=["Patients"]
)

# Dependency to provide the PatientService
def get_patient_service(db=Depends(get_db)) -> PatientService:
    return PatientService(db)

# Define role-based access dependencies
patient_dependency = Depends(RoleChecker(allowed_roles=["Admin", "Patient"]))
nurse_dependency = Depends(RoleChecker(allowed_roles=["Admin", "Nurse"]))
admin_dependency = Depends(RoleChecker(allowed_roles=["Admin"]))


@router.post(
    "/",
    response_model=PatientCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new patient"
)
def register_new_patient(
    patient_in: PatientCreate,
    service: PatientService = Depends(get_patient_service)
):
    """
    Handles public registration of a new patient account.
    """
    try:
        patient_data_dict = patient_in.model_dump(exclude={"address"})
        address_data_dict = patient_in.address.model_dump() if patient_in.address else None
        created_patient = service.create_patient_and_user_account(
            patient_data=patient_data_dict,
            address_data=address_data_dict
        )
        return created_patient
    except HTTPException as e:
        # Assuming service layer raises HTTPException for known errors
        raise e
    except Exception as e:
        print(f"An unexpected error occurred during patient registration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during registration: {str(e)}"
        )


@router.get("/me", response_model=PatientResponse, summary="Get current patient's profile")
def get_my_profile(
    current_user: models.User = patient_dependency,
    service: PatientService = Depends(get_patient_service)
):
    """
    Retrieves the profile for the currently authenticated patient.
    Requires 'Patient' role.
    """
    try:
        patient_profile = service.get_patient_profile(patient_id=current_user.id)
        if not patient_profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found.")
        return patient_profile
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error fetching profile for patient {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching profile."
        )


@router.put("/me", response_model=PatientResponse, summary="Update current patient's profile")
def update_my_profile(
    patient_update_data: PatientUpdate,
    current_user: models.User = patient_dependency,
    service: PatientService = Depends(get_patient_service)
):
    """
    Updates the profile for the currently authenticated patient.
    Requires 'Patient' role.
    """
    try:
        update_dict = patient_update_data.model_dump(exclude_unset=True)
        if not update_dict:
            raise HTTPException(status_code=400, detail="No update data provided.")

        return service.update_patient_profile(patient_id=current_user.id, updates=update_dict)
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error updating profile for patient {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating profile."
        )

@router.get("/all", response_model=list[PatientResponse], summary="Get all patients (Admin Access)")
def get_all_patients(
    service: PatientService = Depends(get_patient_service),
    current_user: models.User = admin_dependency
):
    """
    Retrieves all patients' profiles.
    Requires 'Admin' role.
    """
    try:
        return service.get_all_patients()
    except Exception as e:
        print(f"Error fetching all patients: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching all patients."
        )

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT, summary="Deactivate current patient's account")
def deactivate_my_account(
    current_user: models.User = patient_dependency,
    service: PatientService = Depends(get_patient_service)
):
    """
    Deactivates the account for the currently authenticated patient.
    Requires 'Patient' role.
    """
    try:
        service.deactivate_patient_account(patient_id=current_user.id)
        return None
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error deactivating account for patient {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deactivating account."
        )


@router.get(
    "/one/{patient_id}",
    response_model=PatientResponse,
    summary="Get patient profile by ID (Admin Access)",
    dependencies=[admin_dependency]
)
def get_patient_by_id_as_admin(
    patient_id: uuid.UUID,
    service: PatientService = Depends(get_patient_service)
):
    """
    Retrieves a specific patient's profile by their ID.
    Requires 'Admin' or 'Nurse' role.
    """
    try:
        patient_profile = service.get_patient_profile(patient_id=patient_id)
        if not patient_profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")
        return patient_profile
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error fetching patient profile for ID {patient_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching patient profile."
        )