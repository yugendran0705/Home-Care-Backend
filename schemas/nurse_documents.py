# /schemas/nurse_document.py

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class NurseDocumentBase(BaseModel):
    """
    Base schema for a nurse's document.
    """
    nurse_id: uuid.UUID
    document_type: str = Field(..., examples=["Aadhar", "NursingLicense"])
    document_url: HttpUrl # Pydantic will validate this is a valid URL


class NurseDocumentCreate(NurseDocumentBase):
    """
    Schema for uploading a new document for a nurse.
    """
    pass


class NurseDocumentUpdate(BaseModel):
    """
    Schema for an admin to verify or reject a document.
    """
    verification_status: str = Field(..., examples=["Approved", "Rejected"])
    notes: Optional[str] = Field(None, description="Reason for rejection or other comments.")


class NurseDocumentResponse(NurseDocumentBase):
    """
    Schema for returning a document's details from the API.
    """
    id: uuid.UUID
    verification_status: str
    notes: Optional[str] = None
    uploaded_at: datetime
    verified_at: Optional[datetime] = None

    class Config:
        from_attributes = True

