from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
import uuid
from datetime import datetime

from passlib.context import CryptContext
import models

# Password hashing context (for bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Helper function to hash a password
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

class UserRepository:
    """
    Repository for handling all database operations related to the User model.
    """
    def __init__(self, db: Session):
        self.db = db

    def create_user(
        self,
        email: str,
        password_hash: str,
        user_type: str = "Patient"
    ) -> models.User:
        """
        Creates a new user record in the database.
        Password is automatically hashed before storage.
        """
        db_user = models.User(
            email=email,
            password_hash=password_hash,
            user_type=user_type,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True
        )

        try:
            self.db.add(db_user)
            self.db.commit()
            self.db.refresh(db_user)
            return db_user
        except IntegrityError:
            self.db.rollback()
            raise ValueError("Email already registered.")
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to create user: {e}")

    def get_user_by_id(self, user_id: uuid.UUID) -> Optional[models.User]:
        """
        Retrieves a user by their unique ID.
        """
        return self.db.query(models.User).filter(models.User.id == user_id).first()

    def get_user_by_email(self, email: str) -> Optional[models.User]:
        """
        Retrieves a user by their email address.
        """
        return self.db.query(models.User).filter(models.User.email == email).first()

    def get_all_users(self, skip: int = 0, limit: int = 100) -> List[models.User]:
        """
        Retrieves all users with optional pagination.
        """
        return self.db.query(models.User).offset(skip).limit(limit).all()

    def update_user(self, user_id: uuid.UUID, updates: dict) -> Optional[models.User]:
        """
        Updates an existing user record.
        Handles password hashing if password is in the updates.
        """
        db_user = self.get_user_by_id(user_id)
        if not db_user:
            return None

        # Hash new password if it's being updated
        if 'password' in updates:
            updates['password_hash'] = get_password_hash(updates['password'])
            del updates['password']
        
        # Set updated_at timestamp
        updates['updated_at'] = datetime.utcnow()

        for key, value in updates.items():
            setattr(db_user, key, value)
        
        self.db.commit()
        self.db.refresh(db_user)
        return db_user

    def delete_user(self, user_id: uuid.UUID) -> bool:
        """
        Deletes a user record by ID.
        Returns True if deleted, False if not found.
        """
        db_user = self.get_user_by_id(user_id)
        if not db_user:
            return False
        
        self.db.delete(db_user)
        self.db.commit()
        return True
