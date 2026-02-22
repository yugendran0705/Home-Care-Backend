# /views/address.py

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

# Import dependencies, services, models, and schemas
from config.database import get_db
from utils.roleChecker import RoleChecker
from services.address import AddressService
import models
from schemas.address import AddressCreate, AddressUpdate, AddressResponse

# Create API router
router = APIRouter(
    prefix="/addresses",
    tags=["Addresses"]
)

# Dependency to provide the AddressService
def get_address_service(db=Depends(get_db)) -> AddressService:
    return AddressService(db)

# Define role-based access dependencies (same as in patient views)
user_dependency = Depends(RoleChecker(allowed_roles=["Admin", "Patient", "Nurse"]))
admin_dependency = Depends(RoleChecker(allowed_roles=["Admin"]))


@router.post(
    "/",
    response_model=AddressResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new address for the current user"
)
def create_address_for_user(
    address_in: AddressCreate,
    current_user: models.User = user_dependency,
    service: AddressService = Depends(get_address_service)
):
    """
    Handles the creation of a new address and associates it with the authenticated user.
    """
    try:
        return service.create_address_for_user(
            address_in=address_in,
            user_id=current_user.id
        )
    except ValueError as e:
        print(f"Error creating address for user {current_user.id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        print(f"An unexpected error occurred while creating address: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get(
    "/me",
    response_model=List[AddressResponse],
    summary="Get all addresses for the current user"
)
def get_my_addresses(
    current_user: models.User = user_dependency,
    service: AddressService = Depends(get_address_service)
):
    """
    Retrieves all addresses associated with the currently authenticated user.
    """
    try:
        return service.get_addresses_for_user(user_id=current_user.id)
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error fetching addresses for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching addresses."
        )


@router.get(
    "/one/{address_id}",
    response_model=AddressResponse,
    summary="Get a specific address by ID (User-restricted)",
)
def get_address_by_id(
    address_id: uuid.UUID,
    current_user: models.User = user_dependency,
    service: AddressService = Depends(get_address_service)
):
    """
    Retrieves a specific address by its ID, ensuring it belongs to the authenticated user.
    """
    try:
        db_address = service.get_address_by_id(address_id=address_id)
        if not db_address or db_address.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Address not found or not authorized to view this address."
            )
        return db_address
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error fetching address {address_id} for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching address."
        )


@router.put(
    "/{address_id}",
    response_model=AddressResponse,
    summary="Update an existing address",
)
def update_address(
    address_id: uuid.UUID,
    address_update_data: AddressUpdate,
    current_user: models.User = user_dependency,
    service: AddressService = Depends(get_address_service)
):
    """
    Updates an existing address, ensuring it belongs to the authenticated user.
    """
    try:
        updated_address = service.update_address(
            address_id=address_id,
            address_in=address_update_data,
            user_id=current_user.id
        )
        return updated_address
    except ValueError as e:
        print(f"Error updating address {address_id} for user {current_user.id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        print(f"An unexpected error occurred while updating address: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )


@router.delete(
    "/{address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an address",
)
def delete_address(
    address_id: uuid.UUID,
    current_user: models.User = user_dependency,
    service: AddressService = Depends(get_address_service)
):
    """
    Deletes an address, ensuring it belongs to the authenticated user
    and is not the user's primary address.
    """
    try:
        service.delete_address(address_id=address_id, user_id=current_user.id)
        return None
    except ValueError as e:
        print(f"Error deleting address: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )


@router.patch(
    "/set_primary/{address_id}",
    response_model=AddressResponse,
    summary="Set an address as the primary address for the current user",
)
def set_primary_address(
    address_id: uuid.UUID,
    current_user: models.User = user_dependency,
    service: AddressService = Depends(get_address_service)
):
    """
    Sets a specific address as the primary address, deactivating any existing primary address.
    """
    try:
        updated_address = service.update_primary_address(
            user_id=current_user.id,
            address_id=address_id
        )
        return updated_address
    except ValueError as e:
        print(f"Error setting primary address {address_id} for user {current_user.id}: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        print(f"An unexpected error occurred while setting primary address: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )