# /views/users.py

import uuid
from fastapi import APIRouter, Depends, HTTPException, status

from config.database import get_db
from utils.roleChecker import RoleChecker
from services.users import UserService
import models
from schemas.token import Token, RefreshTokenRequest
from schemas.users import UserCreate, UserLogin, UserResponse, UserUpdate

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
        print(f"Value Error in user registration: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        print(f"Unexpected Error in user registration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during registration."
        )   

@router.post(
    "/login",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="User Login"
)
def login_user(
    login_data: UserLogin,
    service: UserService = Depends(get_user_service)
):
    """
    Handles user login and returns access and refresh tokens
    """
    try:
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
    except HTTPException as e:
        print(f"HTTP Error during login: {e.detail}")
        raise e
    except Exception as e:
        print(f"Unexpected Error during login: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during login."
        )

@router.post(
    "/refresh",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token"
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
        return Token(access_token=new_tokens["access_token"], refresh_token=new_tokens["refresh_token"])
    except ValueError as e:
        print(f"Value Error during token refresh: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        print(f"Unexpected Error during token refresh: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while refreshing the token."
        )


@router.get("/me", response_model=UserResponse, summary="Get current user's profile")
def get_my_profile(
    service: UserService = Depends(get_user_service),
    user: models.User = patient_dependency
):
    """
    Retrieves the profile of the currently logged-in user.
    """
    try:
        return service.get_user_by_id(user.id)
    except HTTPException as e:
        print(f"HTTP Error getting own profile: {e.detail}")
        raise e
    except Exception as e:
        print(f"Unexpected Error getting own profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching your profile."
        )

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
    try:
        user = service.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user
    except HTTPException as e:
        print(f"HTTP Error getting user by ID: {e.detail}")
        raise e
    except Exception as e:
        print(f"Unexpected Error getting user by ID: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching the user profile."
        )

@router.put("/", response_model=UserResponse, summary="Update current user's profile")    
def update_my_profile(
    user_update_data: UserUpdate, # Use UserUpdate schema for partial updates
    service: UserService = Depends(get_user_service),
    user: models.User = patient_dependency
):
    """
    Updates the profile of the currently logged-in user.
    """
    try:
        update_dict = user_update_data.model_dump(exclude_unset=True)
        if not update_dict:
            raise HTTPException(status_code=400, detail="No update data provided.")
        
        updated_user = service.update_user_profile(user.id, update_dict)
        return updated_user
    except HTTPException as e:
        print(f"HTTP Error updating own profile: {e.detail}")
        raise e
    except Exception as e:
        print(f"Unexpected Error updating own profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating your profile."
        )

@router.delete("/", status_code=status.HTTP_204_NO_CONTENT, summary="Deactivate current user's account")
def deactivate_my_account(
    service: UserService = Depends(get_user_service),
    user: models.User = patient_dependency
):
    """
    Deactivates the account of the currently logged-in user.
    """
    try:
        service.deactivate_user(user.id)
        return None
    except HTTPException as e:
        print(f"HTTP Error deactivating account: {e.detail}")
        raise e
    except Exception as e:
        print(f"Unexpected Error deactivating account: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during account deactivation."
        )
