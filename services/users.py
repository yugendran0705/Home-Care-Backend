# /services/users.py

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, Dict
import uuid

from passlib.context import CryptContext
import models
from repositories.users import UserRepository
from config.security import create_access_token, create_refresh_token, verify_token
from jose import JWTError
from utils.redis import delete_cache

# Password hashing context (for bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserService:
    """
    Service for handling all business logic related to the User model.
    This layer orchestrates calls to the UserRepository and contains business rules.
    """
    def __init__(self, db: Session):
        self.user_repo = UserRepository(db)

    def get_password_hash(self, password: str) -> str:
        """
        Hashes a plain-text password using bcrypt.
        """
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verifies a plain-text password against a hashed password.
        """
        return pwd_context.verify(plain_password, hashed_password)

    def create_new_user(
        self,
        email: str,
        password: str,
        user_type: str = "Patient"
    ) -> models.User:
        """
        Business logic to create a new user.
        Checks for an existing user and handles password hashing.
        """
        existing_user = self.user_repo.get_user_by_email(email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered."
            )
        
        hashed_password = self.get_password_hash(password)
        
        user_data = {
            "email": email,
            "password_hash": hashed_password,
            "user_type": user_type
        }
        
        return self.user_repo.create_user(**user_data)

    def get_user_by_id(self, user_id: uuid.UUID) -> Optional[models.User]:
        """
        Retrieves a user from the repository.
        """
        return self.user_repo.get_user_by_id(user_id)

    def get_user_by_email(self, email: str) -> Optional[models.User]:
        """
        Retrieves a user from the repository.
        """
        return self.user_repo.get_user_by_email(email)
    
    def authenticate_user(self, email: str, password: str) -> Optional[Dict[str, str]]:
        """
        Business logic to authenticate a user.

        1. Fetches the user by email.
        2. Verifies the password.
        3. Checks if the user is active.
        4. Creates and returns access and refresh tokens if successful.

        Args:
            email (str): The user's email.
            password (str): The user's plain-text password.

        Returns:
            Optional[Dict[str, str]]: A dictionary with tokens, or None if auth fails.
        """
        user = self.user_repo.get_user_by_email(email)
        
        # Case 1: User does not exist or password is incorrect
        if not user or not self.verify_password(password, user.password_hash):
            return None

        # Case 2: User is inactive
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive."
            )

        # If authentication is successful, create tokens
        token_data = {
            "id": str(user.id)
        }
        
        access_token = create_access_token(data=token_data)
        refresh_token = create_refresh_token(data=token_data)
        
        return {"access_token": access_token, "refresh_token": refresh_token}

    def update_user_profile(self, user_id: uuid.UUID, updates: dict) -> Optional[models.User]:
        """
        Business logic for updating a user's profile.
        Invalidates user cache to ensure fresh data.
        """
        user = self.user_repo.get_user_by_id(user_id)
        if not user:
            return None
        
        # Example of a business rule: can't change email to an existing one
        if 'email' in updates and updates['email'] != user.email:
            existing_user = self.user_repo.get_user_by_email(updates['email'])
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="New email is already in use."
                )
        
        updated_user = self.user_repo.update_user(user.id, updates)
        
        # Invalidate user cache (harmless no-op if user has no cache)
        delete_cache(f"user_{user_id}")
        
        return updated_user

    def deactivate_user(self, user_id: uuid.UUID) -> bool:
        """
        Business logic to deactivate a user account.
        Invalidates user cache to ensure fresh data.
        """
        user = self.user_repo.get_user_by_id(user_id)
        if not user:
            return False
        
        updates = {"is_active": False}
        self.user_repo.update_user(user.id, updates)
        
        # Invalidate user cache (harmless no-op if user has no cache)
        delete_cache(f"user_{user_id}")
        
        return True
    
    def create_access_token_with_refresh_token(self, refresh_token: str) -> Optional[Dict[str, str]]:
        """
        Verifies a refresh token, checks user validity, and returns a new access/refresh token pair.
        """
        try:
            # Step 1: Verify the refresh token's signature and expiration
            payload = verify_token(refresh_token)
            if not payload:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token."
                )

            # Step 2: Extract the user ID from the token
            user_id_str = payload.get("id")
            if not user_id_str:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload."
                )
            
            # Step 3: Check if the user exists and is active
            user_id = uuid.UUID(user_id_str)
            user = self.user_repo.get_user_by_id(user_id)
            if not user or not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or inactive user."
                )
                
            # Step 4: If all checks pass, create and return new tokens
            token_data = {"id": str(user.id)}
            new_access_token = create_access_token(data=token_data)
            new_refresh_token = create_refresh_token(data=token_data)
            
            return {"access_token": new_access_token, "refresh_token": new_refresh_token}

        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format."
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials."
            )
