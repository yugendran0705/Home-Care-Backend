# /repositories/nurse_services.py

import uuid
from typing import List, Optional, Dict, Any
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import select, and_

import models
from schemas.nurse_services import NurseServiceCreate, NurseServiceBulkCreate


class NurseServiceRepository:
    """
    Repository for the NurseService association table.
    """

    def __init__(self, db: Session):
        """
        Initializes the repository with a database session.
        """
        self.db = db

    def add_service_to_nurse(self, *, nurse_service_in: NurseServiceCreate) -> models.NurseService:
        """
        Links a service to a nurse, creating an entry in the junction table.

        Args:
            nurse_service_in (NurseServiceCreate): A Pydantic schema with nurse_id,
                                                   service_id, and an optional custom price.

        Returns:
            models.NurseService: The newly created NurseService association object.
        """
        db_nurse_service = models.NurseService(**nurse_service_in.model_dump())
        
        self.db.add(db_nurse_service)
        self.db.commit()
        self.db.refresh(db_nurse_service)
        return db_nurse_service

    def get_services_for_nurse(self, *, nurse_id: uuid.UUID) -> List[models.NurseService]:
        """
        Retrieves all services offered by a specific nurse.

        Args:
            nurse_id (uuid.UUID): The ID of the nurse.

        Returns:
            List[models.NurseService]: A list of NurseService association objects.
        """
        statement = select(models.NurseService).where(models.NurseService.nurse_id == nurse_id)
        return self.db.execute(statement).scalars().all()

    def get_nurses_for_service(self, *, service_id: uuid.UUID) -> List[models.NurseService]:
        """
        Retrieves all nurses who offer a specific service.

        Args:
            service_id (uuid.UUID): The ID of the service.

        Returns:
            List[models.NurseService]: A list of NurseService association objects.
        """
        statement = select(models.NurseService).where(models.NurseService.service_id == service_id)
        return self.db.execute(statement).scalars().all()

    def get_specific_nurse_service(
        self, *, nurse_id: uuid.UUID, service_id: uuid.UUID
    ) -> Optional[models.NurseService]:
        """
        Finds a specific nurse-service link.

        Args:
            nurse_id (uuid.UUID): The nurse's ID.
            service_id (uuid.UUID): The service's ID.

        Returns:
            Optional[models.NurseService]: The association object if it exists, otherwise None.
        """
        statement = select(models.NurseService).where(
            and_(
                models.NurseService.nurse_id == nurse_id,
                models.NurseService.service_id == service_id,
            )
        )
        return self.db.execute(statement).scalar_one_or_none()

    def remove_service_from_nurse(self, *, nurse_id: uuid.UUID, service_id: uuid.UUID) -> bool:
        """
        Removes a specific service link from a nurse.

        Args:
            nurse_id (uuid.UUID): The nurse's ID.
            service_id (uuid.UUID): The service's ID.

        Returns:
            bool: True if the link was found and deleted, False otherwise.
        """
        db_nurse_service = self.get_specific_nurse_service(
            nurse_id=nurse_id, service_id=service_id
        )
        
        if not db_nurse_service:
            return False
            
        self.db.delete(db_nurse_service)
        self.db.commit()
        return True

    def remove_all_services_from_nurse(self, *, nurse_id: uuid.UUID) -> int:
        """
        Removes all service links for a given nurse.

        Args:
            nurse_id (uuid.UUID): The nurse's ID.

        Returns:
            int: The number of services removed.
        """
        count = (
            self.db.query(models.NurseService)
            .filter(models.NurseService.nurse_id == nurse_id)
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return count

    def update_price(self, *, nurse_id: uuid.UUID, service_id: uuid.UUID, new_price: Decimal) -> Optional[models.NurseService]:
        """
        Updates the price for an existing nurse-service link.

        Args:
            nurse_id (uuid.UUID): The nurse's ID.
            service_id (uuid.UUID): The service's ID.
            new_price (Decimal): The new price to set.

        Returns:
            Optional[models.NurseService]: The updated NurseService object, or None if not found.
        """
        db_nurse_service = self.get_specific_nurse_service(
            nurse_id=nurse_id, service_id=service_id
        )
        
        if not db_nurse_service:
            return None
            
        db_nurse_service.price = new_price
        self.db.add(db_nurse_service)
        self.db.commit()
        self.db.refresh(db_nurse_service)
        return db_nurse_service

    

    def bulk_create_for_nurse(
        self,
        *,
        nurse_service_bulk_create: NurseServiceBulkCreate
    ) -> List[models.NurseService]:
        """
        Bulk creates nurse-service associations for a single nurse.

        Args:
            nurse_service_bulk_create (NurseServiceBulkCreate): The bulk assignment payload.

        Returns:
            List[models.NurseService]: The newly created NurseService associations.
        """
        if not nurse_service_bulk_create.service_ids:
            return []

        db_nurse_services = []
        for service_id in nurse_service_bulk_create.service_ids:
            db_nurse_services.append(
                models.NurseService(
                    nurse_id=nurse_service_bulk_create.nurse_id,
                    service_id=service_id,
                    price=nurse_service_bulk_create.price,
                )
            )

        self.db.add_all(db_nurse_services)
        self.db.commit()

        for service in db_nurse_services:
            self.db.refresh(service)

        return db_nurse_services
