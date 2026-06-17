import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config.database import get_db
from utils.roleChecker import RoleChecker
from services.working_hours import WorkingHoursService
import models
from schemas.working_hours import (
    WorkingHoursCreate,
    WorkingHoursUpdate,
    WorkingHoursResponse,
)

# Create API router
router = APIRouter(
    prefix="/working_hours",
    tags=["WorkingHours"]
)

# Dependency to provide the WorkingHoursService
def get_working_hours_service(db: Session = Depends(get_db)) -> WorkingHoursService:
    return WorkingHoursService(db)

# Define role-based access dependencies
nurse_dependency = Depends(RoleChecker(allowed_roles=["Admin", "Nurse"]))
user_dependency = Depends(RoleChecker(allowed_roles=["Admin", "Nurse", "Patient"]))


@router.post(
    "/",
    response_model=WorkingHoursResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a working hours slot for the current nurse",
)
def create_working_hours_for_nurse(
    working_hours_in: WorkingHoursCreate,
    current_user: models.User = nurse_dependency,
    service: WorkingHoursService = Depends(get_working_hours_service),
):
    """
    Creates a working hours slot for the authenticated nurse.
    """
    try:
        return service.create_working_hours(
            nurse_id=current_user.id,
            working_hours_in=working_hours_in,
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )


@router.post(
    "/bulk",
    response_model=List[WorkingHoursResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create multiple working hours slots for the current nurse",
)
def bulk_create_working_hours_for_nurse(
    working_hours_data: List[WorkingHoursCreate],
    current_user: models.User = nurse_dependency,
    service: WorkingHoursService = Depends(get_working_hours_service),
):
    """
    Creates multiple working hours slots for the authenticated nurse.
    """
    try:
        return service.bulk_create_working_hours(
            nurse_id=current_user.id,
            working_hours_data=working_hours_data,
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )


@router.get(
    "/one/{working_hours_id}",
    response_model=WorkingHoursResponse,
    summary="Get a specific working hours slot by ID",
    status_code=status.HTTP_200_OK,
)
def get_working_hours_by_id(
    working_hours_id: uuid.UUID,
    service: WorkingHoursService = Depends(get_working_hours_service),
    current_user: models.User = user_dependency,
):
    """
    Retrieves a single working hours record by its ID.
    This endpoint is available to all authenticated users.
    """
    try:
        return service.get_working_hours_by_id(working_hours_id=working_hours_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )


@router.get(
    "/nurse/{nurse_id}",
    response_model=List[WorkingHoursResponse],
    summary="Get working hours for a nurse",
    status_code=status.HTTP_200_OK,
)
def get_working_hours_for_nurse(
    nurse_id: uuid.UUID,
    service: WorkingHoursService = Depends(get_working_hours_service),
    current_user: models.User = user_dependency,
):
    """
    Retrieves all working hours slots for a nurse.
    A patient, nurse, or admin may view nurse availability.
    """
    try:
        return service.get_working_hours_for_nurse(nurse_id=nurse_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )


@router.put(
    "/{working_hours_id}",
    response_model=WorkingHoursResponse,
    summary="Update a working hours slot",
    status_code=status.HTTP_200_OK,
)
def update_working_hours(
    working_hours_id: uuid.UUID,
    working_hours_update: WorkingHoursUpdate,
    current_user: models.User = nurse_dependency,
    service: WorkingHoursService = Depends(get_working_hours_service),
):
    """
    Updates a working hours slot.
    Nurses may only update their own records.
    """
    try:
        existing = service.get_working_hours_by_id(working_hours_id=working_hours_id)
        if current_user.user_type == "Nurse" and current_user.id != existing.nurse_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Nurses may only update their own working hours.",
            )

        return service.update_working_hours(
            working_hours_id=working_hours_id,
            updates=working_hours_update,
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )


@router.delete(
    "/{working_hours_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a working hours slot",
)
def delete_working_hours(
    working_hours_id: uuid.UUID,
    current_user: models.User = nurse_dependency,
    service: WorkingHoursService = Depends(get_working_hours_service),
):
    """
    Deletes a working hours slot.
    Nurses may only delete their own records.
    """
    try:
        existing = service.get_working_hours_by_id(working_hours_id=working_hours_id)
        if current_user.user_type == "Nurse" and current_user.id != existing.nurse_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Nurses may only delete their own working hours.",
            )

        service.delete_working_hours(working_hours_id=working_hours_id)
        return {"detail": "Working hours deleted successfully."}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )
