# /views/nurse_services.py

import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status

# Import dependencies, services, models, and schemas
from config.database import get_db
from utils.roleChecker import RoleChecker
from services.nurse_services import NurseServiceService
import models
from schemas.nurse_services import NurseServiceBulkCreate, NurseServiceBulkResponse, NurseServiceResponse, NurseServiceUpdate, NurseServicesResponse

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
    "/services",
    response_model=NurseServiceBulkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign multiple services to a nurse"
)
async def assign_service_to_nurse(
    service_in: NurseServiceBulkCreate,
    current_user: models.User = nurse_dependency,
    service: NurseServiceService = Depends(get_nurse_service_service)
):
    """
    Assigns multiple services to a specific nurse using a single bulk request.
    Only nurses can assign services to themselves; admins can assign to any nurse.
    """
    user_role = getattr(current_user, "user_type", None)
    if user_role != "Admin":
        service_in = service_in.model_copy(update={"nurse_id": current_user.id})

    try:
        bulk_response = service.assign_service_to_nurse(
            nurse_service_in=service_in
        )
        return bulk_response
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get(
    "/{nurse_id}/services",
    response_model=NurseServicesResponse,
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
    current_user: models.User = nurse_dependency,
    service: NurseServiceService = Depends(get_nurse_service_service)
):
    """
    Updates the custom price for a service offered by a nurse.
    Only nurses and admins can perform this action.
    """
    user_role = getattr(current_user, "user_type", None)
    if user_role != "Admin" and nurse_id != getattr(current_user, "id", None):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nurses can only update prices for their own services."
        )

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
    "/{nurse_id}/services",
    status_code=status.HTTP_200_OK,
    summary="Remove all services from a nurse's profile"
)
async def remove_service_from_nurse(
    nurse_id: uuid.UUID,
    current_user: models.User = nurse_dependency,
    service: NurseServiceService = Depends(get_nurse_service_service)
):
    """
    Removes all services from a specific nurse's profile.
    Only nurses can remove their own services, admins can remove from any nurse.
    """
    try:
        count = service.remove_service_from_nurse(
            nurse_id=nurse_id,
            current_user_id=current_user.id
        )
        return {"detail": f"Successfully removed {count} service(s) from nurse."}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )