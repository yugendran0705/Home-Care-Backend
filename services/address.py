# /services/address.py

import uuid
from decimal import Decimal
from typing import List, Optional, Dict, Any

from geoalchemy2.elements import WKTElement
from repositories.address import AddressRepository
from repositories.patients import PatientRepository
from schemas.address import AddressCreate, AddressUpdate
from models import Address as AddressModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from utils.redis import delete_cache


class AddressService:
    """
    Service layer for handling address-related business logic.
    """

    def __init__(self, db: Session):
        """
        Initializes the service with a database session and a repository instance.
        """
        self.address_repo = AddressRepository(db)
        self.db = db
        self.patient_repo = PatientRepository(db)

    @staticmethod
    def _build_location(
        latitude: Optional[Decimal],
        longitude: Optional[Decimal]
    ) -> Optional[WKTElement]:
        """
        Builds a PostGIS POINT from latitude/longitude.
        """
        if latitude is None and longitude is None:
            return None

        if latitude is None or longitude is None:
            raise ValueError("Both latitude and longitude must be provided together.")

        return WKTElement(f"POINT({float(longitude)} {float(latitude)})", srid=4326)

    def create_address_for_user(self, address_in: AddressCreate, user_id: uuid.UUID) -> AddressModel:
        """
        Creates a new address and associates it with a user.
        Invalidates user cache to ensure fresh data.
        """
        address_data = address_in.model_dump()
        address_data["user_id"] = user_id
        address_data["location"] = self._build_location(
            latitude=address_data.get("latitude"),
            longitude=address_data.get("longitude")
        )
        
        try:
            new_address = self.address_repo.create(address_data=address_data)
            
            # Invalidate user cache (harmless no-op if user has no cache)
            delete_cache(f"user_{user_id}")
            
            return new_address
        except IntegrityError:
            raise ValueError("An integrity error occurred while creating the address.")

    def get_address_by_id(self, address_id: uuid.UUID) -> Optional[AddressModel]:
        """
        Retrieves a single address by its ID.
        """
        return self.address_repo.get_by_id(address_id=address_id)

    def get_addresses_for_user(self, user_id: uuid.UUID) -> List[AddressModel]:
        """
        Retrieves all addresses associated with a specific user.
        """
        return self.address_repo.get_by_user_id(user_id=user_id)

    def update_address(
        self, address_id: uuid.UUID, address_in: AddressUpdate, user_id: uuid.UUID
    ) -> AddressModel:
        """
        Updates an address's details and handles the 'is_primary' business logic.
        Invalidates user cache to ensure fresh data.
        """
        db_address = self.get_address_by_id(address_id=address_id)
        if not db_address or db_address.user_id != user_id:
             raise ValueError("Address not found or not authorized to update.")

        update_data = address_in.model_dump(exclude_unset=True)

        if "latitude" in update_data or "longitude" in update_data:
            final_latitude = update_data.get("latitude", db_address.latitude)
            final_longitude = update_data.get("longitude", db_address.longitude)
            update_data["location"] = self._build_location(
                latitude=final_latitude,
                longitude=final_longitude
            )

        if update_data.get("is_primary") is True:
            self.address_repo.deactivate_all_primary_addresses_for_user(user_id)

        updated_address = self.address_repo.update(
            address=db_address,
            updates=update_data
        )

        # Invalidate user cache (harmless no-op if user has no cache)
        delete_cache(f"user_{user_id}")

        return updated_address

    def delete_address(self, address_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """
        Deletes an address, with business logic to prevent deleting a primary address.
        Invalidates user cache to ensure fresh data.
        """
        db_address = self.get_address_by_id(address_id=address_id)
        if not db_address or db_address.user_id != user_id:
            raise ValueError("Address not found or not authorized to delete.")
            
        if db_address.is_primary:
            raise ValueError("Cannot delete a primary address. Please set another as primary first.")

        result = self.address_repo.delete(address=db_address)
        
        # Invalidate user cache (harmless no-op if user has no cache)
        if result:
            delete_cache(f"user_{user_id}")
        
        return result
    
    def update_primary_address(self, user_id: uuid.UUID, address_id: uuid.UUID) -> AddressModel:
        """
        Updates the primary address for a user, ensuring only one address can be primary.
        The system relies on addresses.is_primary to identify the primary address.
        Invalidates user cache to prevent stale address data.
        """
        db_address = self.get_address_by_id(address_id=address_id)
        if not db_address or db_address.user_id != user_id:
            raise ValueError("Address not found or not authorized to update.")

        self.address_repo.deactivate_all_primary_addresses_for_user(user_id)
        
        updated_address = self.address_repo.update(
            address=db_address,
            updates={"is_primary": True}
        )

        # Invalidate user cache (harmless no-op if user has no cache)
        delete_cache(f"user_{user_id}")

        return updated_address