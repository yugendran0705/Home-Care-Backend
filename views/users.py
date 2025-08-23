# /views/users.py

import uuid
from fastapi import APIRouter, Depends, HTTPException, status

from config.database import get_db
from utils.roleChecker import RoleChecker
from services.users import UserService
import models
from schemas.token import *
from schemas.users import *

# Create API router
router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

# Dependency to provide the UserService
def get_user_service(db=Depends(get_db)) -> UserService:
    return UserService(db)

# Define role-based access dependencies
patient_dependency = Depends(RoleChecker(allowed_roles=["Admin", "Patient"]))
nurse_dependency = Depends(RoleChecker(allowed_roles=["Admin", "Nurse"]))
admin_dependency = Depends(RoleChecker(allowed_roles=["Admin"]))

@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user"
)
def register_new_user(
    user_in: UserCreate,
    service: UserService = Depends(get_user_service)
):
    """
    Handles public registration of a new user account.
    """
    try:
        created_user = service.create_new_user(
            email=user_in.email,
            password=user_in.password,
            user_type=user_in.user_type
        )
        return created_user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during registration: {str(e)}"
        )   

@router.post(
    "/login",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Register a new patient"
)
def login_user(
    login_data: UserLogin,
    service: UserService = Depends(get_user_service)
):
    """
    Handles user login and returns access and refresh tokens
    """
    response = service.authenticate_user(
        email=login_data.email,
        password=login_data.password
    )
    
    if not response:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    return Token(access_token= response["access_token"], refresh_token= response["refresh_token"])

@router.post(
    "/refresh",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token using a refresh token"
)
def refresh_token(
    refresh_token_in: RefreshTokenRequest,
    service: UserService = Depends(get_user_service)
):
    """
    Exchanges a valid refresh token for a new pair of access and refresh tokens.
    """
    try:
        new_tokens = service.create_access_token_with_refresh_token(
            refresh_token=refresh_token_in.refresh_token
        )
        if not new_tokens:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials."
            )
        return Token(access_token=new_tokens["access_token"], refresh_token=new_tokens["refresh_token"])
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/me", response_model=UserResponse, summary="Get current user's profile")
def get_my_profile(
    service: UserService = Depends(get_user_service),
    user: models.User = patient_dependency
):
    """
    Retrieves the profile of the currently logged-in user.
    """
    return service.get_user_by_id(user.id)

@router.get(
    "/one/{user_id}",
    response_model=UserResponse,
    summary="Get user profile by ID (Admin Access)",
    dependencies=[admin_dependency]
)
def get_user_by_id_as_admin(
    user_id: uuid.UUID,
    service: UserService = Depends(get_user_service)
):
    """
    Retrieves a user profile by ID, accessible only to Admins.
    """
    user = service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

@router.put("/me", response_model=UserResponse, summary="Update current user's profile")    
def update_my_profile(
    user_update_data: UserResponse,
    service: UserService = Depends(get_user_service),
    user: models.User = patient_dependency
):
    """
    Updates the profile of the currently logged-in user.
    """
    updated_user = service.update_user_profile(user.id, user_update_data.model_dump())
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return updated_user

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT, summary="Deactivate current user's account")
def deactivate_my_account(
    service: UserService = Depends(get_user_service),
    user: models.User = patient_dependency
):
    """
    Deactivates the account of the currently logged-in user.
    """
    service.deactivate_user(user.id)
    return None