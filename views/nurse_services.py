# /views/nurse_services.py

import uuid
from typing import List
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status

# Import dependencies, services, models, and schemas
from config.database import get_db
from utils.roleChecker import RoleChecker
from services.nurse_services import NurseServiceService
import models
from schemas.nurse_services import NurseServiceCreate, NurseServiceResponse, NurseServiceUpdate

# Create API router
router = APIRouter(
    prefix="/nurses",
    tags=["Nurse Services"]
)

# Dependency to provide the NurseServiceService
def get_nurse_service_service(db=Depends(get_db)) -> NurseServiceService:
    return NurseServiceService(db)

# Define role-based access dependencies
nurse_dependency = Depends(RoleChecker(allowed_roles=["Admin", "Nurse"]))
admin_dependency = Depends(RoleChecker(allowed_roles=["Admin"]))


@router.post(
    "/{nurse_id}/services",
    response_model=NurseServiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign a service to a nurse",
    dependencies=[nurse_dependency]
)
async def assign_service_to_nurse(
    nurse_id: uuid.UUID,
    service_in: NurseServiceCreate,
    service: NurseServiceService = Depends(get_nurse_service_service)
):
    """
    Assigns a service to a nurse with an optional custom price.
    Only nurses and admins can perform this action.
    """
    # Ensure the nurse_id in the path matches the one in the body
    if service_in.nurse_id != nurse_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nurse ID in path must match nurse ID in request body."
        )

    try:
        created_association = service.assign_service_to_nurse(nurse_service_in=service_in)
        return NurseServiceResponse.model_validate(created_association)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get(
    "/{nurse_id}/services",
    response_model=List[NurseServiceResponse],
    summary="Get all services offered by a nurse"
)
async def get_nurse_services(
    nurse_id: uuid.UUID,
    service: NurseServiceService = Depends(get_nurse_service_service)
):
    """
    Retrieves all services offered by a specific nurse.
    """
    try:
        nurse_services = service.get_services_for_nurse(nurse_id=nurse_id)
        return nurse_services
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )


@router.put(
    "/{nurse_id}/services/{service_id}",
    response_model=NurseServiceResponse,
    summary="Update the price for a nurse-service link",
    dependencies=[nurse_dependency]
)
async def update_nurse_service_price(
    nurse_id: uuid.UUID,
    service_id: uuid.UUID,
    price_update: NurseServiceUpdate,
    service: NurseServiceService = Depends(get_nurse_service_service)
):
    """
    Updates the custom price for a service offered by a nurse.
    Only nurses and admins can perform this action.
    """
    try:
        updated_association = service.update_service_price(
            nurse_id=nurse_id,
            service_id=service_id,
            new_price=price_update.price
        )
        return NurseServiceResponse.model_validate(updated_association)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )


@router.delete(
    "/{nurse_id}/services/{service_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a service from a nurse's profile",
    dependencies=[nurse_dependency]
)
async def remove_service_from_nurse(
    nurse_id: uuid.UUID,
    service_id: uuid.UUID,
    service: NurseServiceService = Depends(get_nurse_service_service)
):
    """
    Removes a service from a nurse's profile.
    Only nurses and admins can perform this action.
    """
    try:
        service.remove_service_from_nurse(nurse_id=nurse_id, service_id=service_id)
        return {"detail": "Service removed from nurse successfully."}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )