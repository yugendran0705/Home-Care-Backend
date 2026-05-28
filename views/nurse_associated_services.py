# /views/nurse_associated_services.py

import uuid
from fastapi import APIRouter, Depends, HTTPException, status

# Import dependencies, services, models, and schemas
from config.database import get_db
from utils.roleChecker import RoleChecker
from services.nurse_associated_services import NurseAssociatedServiceService
import models
from schemas.nurse_associated_services import NurseAssociatedServiceBulkCreate, NurseAssociatedServicesResponse

# Create API router
router = APIRouter(
    prefix="/nurses",
    tags=["NurseAssociatedServices"]
)

# Dependency to provide the NurseAssociateService
def get_nurse_service_associate(db=Depends(get_db)) -> NurseAssociatedServiceService:
    return NurseAssociatedServiceService(db)

# Define role-based access dependencies
nurse_dependency = Depends(RoleChecker(allowed_roles=["Admin", "Nurse"]))
admin_dependency = Depends(RoleChecker(allowed_roles=["Admin"]))
user_dependency = Depends(RoleChecker(allowed_roles=["Admin", "Nurse", "Patient"]))


@router.post(
    "/services",
    response_model=NurseAssociatedServicesResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign multiple services to a nurse"
)
async def assign_service_to_nurse(
    service_in: NurseAssociatedServiceBulkCreate,
    current_user: models.User = nurse_dependency,
    service: NurseAssociatedServiceService = Depends(get_nurse_service_associate)
):
    """
    Assigns multiple services to a specific nurse using a single bulk request.
    Only nurses can assign services to themselves. 
    """
    try:
        bulk_response = service.assign_service_to_nurse(
            nurse_id=current_user.id,
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
    response_model=NurseAssociatedServicesResponse,
    dependencies=[user_dependency],
    summary="Get all services offered by a nurse"
)
async def get_nurse_services(
    nurse_id: uuid.UUID,
    service: NurseAssociatedServiceService = Depends(get_nurse_service_associate)
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
    "/services",
    response_model=NurseAssociatedServicesResponse,
    summary="Update services for a nurse",
    status_code=status.HTTP_200_OK
)
async def update_nurse_services(
    service_in: NurseAssociatedServiceBulkCreate,
    current_user: models.User = nurse_dependency,
    service: NurseAssociatedServiceService = Depends(get_nurse_service_associate),
):
    """
    Updates the services offered by a nurse.
    Only nurses can update their own services; admins can update any nurse's services.
    """
    try:
        updated_association = service.update_services_for_nurse(
            nurse_id=current_user.id,
            service_ids=service_in.service_ids,
        )
        return NurseAssociatedServicesResponse.model_validate(updated_association)
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
    dependencies=[admin_dependency],
    summary="Remove all services from a nurse's profile"
)
async def remove_service_from_nurse(
    nurse_id: uuid.UUID,
    service: NurseAssociatedServiceService = Depends(get_nurse_service_associate)
):
    """
    Removes all services from a specific nurse's profile.
    Only admins can perform this action.
    """
    try:
        service.remove_service_from_nurse(
            nurse_id=nurse_id
        )
        return {"detail": "Successfully removed all services from nurse."}
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Unexpected error while removing services : {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )
        