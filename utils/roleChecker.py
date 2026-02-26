# /utils/roleChecker.py

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Annotated

from config.database import get_db
from config.security import verify_token
from repositories.users import UserRepository
import models

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/users/login"
)  # Use your actual token URL

db_dependency = Annotated[Session, Depends(get_db)]


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    """
    Decodes token, retrieves user, and checks if they are active.
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credential",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Correctly instantiate the repository to fetch the user
    user_repo = UserRepository(db)
    user = user_repo.get_user_by_id(user_id=user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


class RoleChecker:
    """
    A dependency class to check for user roles.
    """

    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: models.User = Depends(get_current_user)) -> models.User:
        """
        Returns the user if they have the required role, otherwise raises an exception.
        """
        if user.user_type not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {self.allowed_roles}",
            )
        return user  # Return the user object on success
