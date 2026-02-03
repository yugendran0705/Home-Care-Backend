# /repositories/nurse_documents.py

import uuid
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import select, and_

import models
# You will need to create this schema file
from schemas.nurse_documents import NurseDocumentCreate 


class NurseDocumentRepository:
    """
    Repository for handling all database operations for the NurseDocument model.
    """

    def __init__(self, db: Session):
        """
        Initializes the repository with a database session.
        """
        self.db = db

    def get_for_nurse_by_type(
        self, *, nurse_id: uuid.UUID, document_type: str
    ) -> Optional[models.NurseDocument]:
        """
        Retrieves a specific document for a nurse based on its type.
        """
        statement = select(models.NurseDocument).where(
            and_(
                models.NurseDocument.nurse_id == nurse_id,
                models.NurseDocument.document_type == document_type,
            )
        )
        return self.db.execute(statement).scalar_one_or_none()

    def create(self, *, document_in: NurseDocumentCreate) -> models.NurseDocument:
        """
        Creates a new document record for a nurse.

        Enforces the business rule that a nurse can only have one document
        of each type.
        """
        # --- Business Rule Enforcement ---
        existing_doc = self.get_for_nurse_by_type(
            nurse_id=document_in.nurse_id,
            document_type=document_in.document_type
        )
        if existing_doc:
            raise ValueError(
                f"A document of type '{document_in.document_type}' already exists for this nurse."
            )
        # --- End of Business Rule ---

        db_document = models.NurseDocument(**document_in.model_dump())
        
        self.db.add(db_document)
        self.db.commit()
        self.db.refresh(db_document)
        return db_document

    def get_by_id(self, *, document_id: uuid.UUID) -> Optional[models.NurseDocument]:
        """
        Retrieves a document by its primary key.
        """
        return self.db.get(models.NurseDocument, document_id)

    def get_for_nurse(self, *, nurse_id: uuid.UUID) -> List[models.NurseDocument]:
        """
        Retrieves all documents for a specific nurse.
        """
        statement = select(models.NurseDocument).where(models.NurseDocument.nurse_id == nurse_id)
        return self.db.execute(statement).scalars().all()

    def update(self, *, document_id: uuid.UUID, updates: Dict[str, Any]) -> Optional[models.NurseDocument]:
        """
        Updates a document's details, primarily for verification by an admin.
        """
        db_document = self.get_by_id(document_id=document_id)
        if not db_document:
            return None
            
        for key, value in updates.items():
            setattr(db_document, key, value)
            
        self.db.add(db_document)
        self.db.commit()
        self.db.refresh(db_document)
        return db_document

    def delete(self, *, document_id: uuid.UUID) -> Optional[models.NurseDocument]:
        """
        Deletes a document record.
        """
        db_document = self.get_by_id(document_id=document_id)
        if not db_document:
            return None
            
        self.db.delete(db_document)
        self.db.commit()
        return db_document
