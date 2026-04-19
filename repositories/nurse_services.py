# /repositories/nurse_services.py

import uuid
from typing import List, Optional

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, and_

import models


class NurseServiceRepository:
    """
    Repository for the NurseService association table.
    """

    def __init__(self, db: Session):
        """
        Initializes the repository with a database session.
        """
        self.db = db

    def get_one(self, *, nurse_id: uuid.UUID, service_id: uuid.UUID) -> Optional[models.NurseService]:
        """
        Retrieves a single nurse-service association by nurse_id and service_id.

        Args:
            nurse_id (uuid.UUID): The ID of the nurse.
            service_id (uuid.UUID): The ID of the service.
        Returns:
            Optional[models.NurseService]: The NurseService association object if found, else None.
        """
        statement = select(models.NurseService).options(
            selectinload(models.NurseService.nurse),
            selectinload(models.NurseService.service)
        ).where(
            and_(
                models.NurseService.nurse_id == nurse_id,
                models.NurseService.service_id == service_id
            )
        )
        return self.db.execute(statement).scalar_one_or_none()

    def get_by_nurse(self, *, nurse_id: uuid.UUID) -> List[models.NurseService]:
        """
        Retrieves all services offered by a specific nurse.

        Args:
            nurse_id (uuid.UUID): The ID of the nurse.

        Returns:
            List[models.NurseService]: A list of NurseService association objects.
        """
        statement = select(models.NurseService).options(
            selectinload(models.NurseService.nurse),
            selectinload(models.NurseService.service)
        ).where(models.NurseService.nurse_id == nurse_id)
        return self.db.execute(statement).scalars().all()

    def get_by_service(self, *, service_id: uuid.UUID) -> List[models.NurseService]:
        """
        Retrieves all nurses who offer a specific service.

        Args:
            service_id (uuid.UUID): The ID of the service.

        Returns:
            List[models.NurseService]: A list of NurseService association objects.
        """
        statement = select(models.NurseService).options(
            selectinload(models.NurseService.nurse),
            selectinload(models.NurseService.service)
        ).where(models.NurseService.service_id == service_id)
        return self.db.execute(statement).scalars().all()

    def delete_all_by_nurse(self, *, nurse_id: uuid.UUID) -> int:
        """
        Removes all service links for a given nurse.

        Args:
            nurse_id (uuid.UUID): The nurse's ID.

        Returns:
            int: The number of services removed.
        """
        try:
            self.db.query(models.NurseService)\
                .filter(models.NurseService.nurse_id == nurse_id)\
                .delete(synchronize_session=False)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return True

    def bulk_create_for_nurse(
        self,
        *,
        nurse_id: uuid.UUID,
        service_ids: List[uuid.UUID]
    ) -> List[models.NurseService]:
        """
        Bulk creates nurse-service associations for a single nurse.

        Args:
            nurse_id (uuid.UUID): The ID of the nurse.
            service_ids (List[uuid.UUID]): List of service IDs to assign to the nurse.

        Returns:
            List[models.NurseService]: The newly created NurseService associations.
        
        Raises:
            Exception: If there's a database integrity error (e.g., duplicate entries, invalid IDs).
        """
        if not service_ids:
            return []

        db_nurse_services = []
        for service_id in service_ids:
            db_nurse_services.append(
                models.NurseService(
                    nurse_id=nurse_id,
                    service_id=service_id
                )
            )

        self.db.add_all(db_nurse_services)
        try:  
            self.db.commit()  
        except Exception:  
            self.db.rollback()  
            raise

        # Fetch the created records with relationships loaded
        statement = select(models.NurseService).options(
            selectinload(models.NurseService.nurse),
            selectinload(models.NurseService.service)
        ).where(
            and_(
                models.NurseService.nurse_id == nurse_id,
                models.NurseService.service_id.in_(service_ids)
            )
        )
        return self.db.execute(statement).scalars().all()
    
    def get_all(self) -> List[models.NurseService]:
        """
        Retrieves all nurse-service associations.

        Returns:
            List[models.NurseService]: A list of all NurseService association objects.
        """
        statement = select(models.NurseService).options(
            selectinload(models.NurseService.nurse),
            selectinload(models.NurseService.service)
        )
        return self.db.execute(statement).scalars().all()
    
    def replace_services_for_nurse(
        self,
        *,
        nurse_id: uuid.UUID,
        service_ids: List[uuid.UUID]
    ) -> List[models.NurseService]:
        """
        Atomically replaces all services for a nurse in a single transaction.
        Deletes existing associations and creates new ones without intermediate commits.

        Args:
            nurse_id (uuid.UUID): The ID of the nurse.
            service_ids (List[uuid.UUID]): List of service IDs to assign to the nurse.

        Returns:
            List[models.NurseService]: The newly created NurseService associations.
        
        Raises:
            Exception: If there's a database integrity error (e.g., duplicate entries, invalid IDs).
        """
        try:
            # Delete existing associations
            self.db.query(models.NurseService)\
                .filter(models.NurseService.nurse_id == nurse_id)\
                .delete(synchronize_session=False)
            
            # Create new associations if any service_ids provided
            if service_ids:
                db_nurse_services = []
                for service_id in service_ids:
                    db_nurse_services.append(
                        models.NurseService(
                            nurse_id=nurse_id,
                            service_id=service_id
                        )
                    )
                self.db.add_all(db_nurse_services)
            
            # Single commit for both operations
            self.db.commit()
            
            # Fetch the created records with relationships loaded
            if service_ids:
                statement = select(models.NurseService).options(
                    selectinload(models.NurseService.nurse),
                    selectinload(models.NurseService.service)
                ).where(
                    and_(
                        models.NurseService.nurse_id == nurse_id,
                        models.NurseService.service_id.in_(service_ids)
                    )
                )
                return self.db.execute(statement).scalars().all()
            else:
                return []
        except Exception:
            self.db.rollback()
            raise
