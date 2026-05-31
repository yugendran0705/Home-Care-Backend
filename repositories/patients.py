from sqlalchemy.orm import Session, joinedload, selectinload
from typing import List, Optional
import uuid
import models

class PatientRepository:
    """
    Repository for handling all direct database operations related to the Patient model.
    This layer does not contain business logic.
    """
    def __init__(self, db: Session):
        self.db = db

    def create(self, patient_data: dict) -> models.Patient:
        """
        Creates a new patient record in the database.
        Expects a dictionary of patient data, including the user_id.
        """
        db_patient = models.Patient(**patient_data)
        self.db.add(db_patient)
        self.db.commit()
        self.db.refresh(db_patient)
        return db_patient

    def get_by_id(self, patient_id: uuid.UUID) -> Optional[models.Patient]:
        """
        Retrieves a patient by their unique ID with eager loading of relationships.
        """
        return (
            self.db.query(models.Patient)
            .options(joinedload(models.Patient.user).selectinload(models.User.addresses))
            .filter(models.Patient.id == patient_id)
            .first()
        )

    def get_all(self, skip: int = 0, limit: int = 100) -> List[models.Patient]:
        """
        Retrieves all patients with optional pagination and eager loading of relationships.
        """
        return (
            self.db.query(models.Patient)
            .options(joinedload(models.Patient.user).selectinload(models.User.addresses))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update(self, patient: models.Patient, updates: dict) -> models.Patient:
        """
        Updates an existing patient record.
        """
        for key, value in updates.items():
            setattr(patient, key, value)
        
        self.db.commit()
        self.db.refresh(patient)
        return patient

    def delete(self, patient: models.Patient) -> None:
        """
        Deletes a patient record.
        """
        self.db.delete(patient)
        self.db.commit()