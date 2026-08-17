# /repositories/address.py

import uuid
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import select

import models

class AddressRepository:
    """
    Repository for handling all direct database operations related to the Address model.
    This layer does not contain business logic.
    """
    def __init__(self, db: Session):
        self.db = db

    def create(self, address_data: Dict[str, Any]) -> models.Address:
        """
        Creates a new address record in the database.
        Expects a dictionary of address data.
        """
        db_address = models.Address(**address_data)
        self.db.add(db_address)
        self.db.commit()
        self.db.refresh(db_address)
        return db_address

    def get_by_id(self, address_id: uuid.UUID) -> Optional[models.Address]:
        """
        Retrieves an address by its unique ID.
        """
        return self.db.query(models.Address).filter(models.Address.id == address_id).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[models.Address]:
        """
        Retrieves all addresses with optional pagination.
        """
        return self.db.query(models.Address).offset(skip).limit(limit).all()

    def get_by_user_id(self, user_id: uuid.UUID) -> List[models.Address]:
        """
        Retrieves all addresses associated with a specific user.
        """
        return self.db.query(models.Address).filter(models.Address.user_id == user_id).all()

    def get_primary_for_user(self, user_id: uuid.UUID) -> Optional[models.Address]:
        """
        Retrieves the user's primary address, or None if they don't have one.
        """
        return (
            self.db.query(models.Address)
            .filter(
                models.Address.user_id == user_id,
                models.Address.is_primary == True,
            )
            .first()
        )

    def update(self, address: models.Address, updates: Dict[str, Any]) -> models.Address:
        """
        Updates an existing address record.
        """
        for key, value in updates.items():
            setattr(address, key, value)
        
        self.db.commit()
        self.db.refresh(address)
        return address

    def delete(self, address: models.Address) -> None:
        """
        Deletes a patient record.
        """
        self.db.delete(address)
        self.db.commit()

    def deactivate_all_primary_addresses_for_user(self, user_id: uuid.UUID) -> None:
        """
        Sets all addresses for a user to non-primary.
        """
        addresses = self.db.query(models.Address).filter(
            models.Address.user_id == user_id,
            models.Address.is_primary == True
        ).all()

        for addr in addresses:
            addr.is_primary = False
            self.db.add(addr)
        
        self.db.commit()