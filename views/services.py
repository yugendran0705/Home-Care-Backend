
# /views/services.py

import uuid
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# Import dependencies, services, and schemas
from config.database import get_db
from utils.roleChecker import RoleChecker
from services.services import ServiceService
from schemas.services import ServiceCreate, ServiceUpdate, ServiceResponse
import models

# Create API router
router = APIRouter(
    prefix="/services",
    tags=["Services"]
)

# Dependency to provide the ServiceService
def get_service_service(db: Session = Depends(get_db)) -> ServiceService:
    return ServiceService(db)

# Define role-based access for admin-only endpoints
admin_dependency = Depends(RoleChecker(allowed_roles=["Admin"]))
user_dependency = Depends(RoleChecker(allowed_roles=["Admin", "Patient", "Nurse"]))

@router.post(
    "/",
    response_model=ServiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new service (Admin Access)"
)
def create_new_service(
    service_in: ServiceCreate,
    service: ServiceService = Depends(get_service_service),
    current_user: models.User = admin_dependency  # Enforce admin role
):
    """
    Handles the creation of a new service that can be offered.
    Requires 'Admin' role.
    """
    return service.create_service(service_in=service_in)

@router.get(
    "/all",
    response_model=List[ServiceResponse],
    summary="List all available services",
)
def list_all_services(
    skip: int = 0,
    limit: int = 100,
    service: ServiceService = Depends(get_service_service),
    status_code=status.HTTP_200_OK
):
    """
    Retrieves a paginated list of all services.
    This is a public endpoint.
    """
    return service.list_all_services(skip=skip, limit=limit)

@router.get(
    "/one/{service_id}",
    response_model=ServiceResponse,
    summary="Get a specific service by ID",
    status_code=status.HTTP_200_OK
)
def get_service_by_id(
    service_id: uuid.UUID,
    service: ServiceService = Depends(get_service_service)
):
    """
    Retrieves details for a specific service by its unique ID.
    This is a public endpoint.
    """
    return service.get_service_by_id(service_id=service_id)

@router.put(
    "/{service_id}",
    response_model=ServiceResponse,
    summary="Update a service (Admin Access)",
    status_code=status.HTTP_200_OK,
)
def update_existing_service(
    service_id: uuid.UUID,
    service_update: ServiceUpdate,
    service: ServiceService = Depends(get_service_service),
    current_user: models.User = admin_dependency  # Enforce admin role
):
    """
    Updates the details of an existing service.
    Requires 'Admin' role.
    """
    return service.update_service(service_id=service_id, updates=service_update)

@router.delete(
    "/{service_id}",
    status_code=status.HTTP_200_OK,
    response_model=Dict[str, str],
    summary="Delete a service (Admin Access)",
)
def delete_existing_service(
    service_id: uuid.UUID,
    service: ServiceService = Depends(get_service_service),
    current_user: models.User = admin_dependency  # Enforce admin role
):
    """
    Deletes a service from the system.
    Requires 'Admin' role.
    """
    return service.delete_service(service_id=service_id)
