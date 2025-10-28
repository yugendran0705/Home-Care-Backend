# /schemas/review.py

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, validator


class ReviewBase(BaseModel):
    """
    Base schema for a review, containing fields provided by the user.
    """
    booking_id: uuid.UUID
    patient_id: uuid.UUID
    nurse_id: uuid.UUID
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    comment: Optional[str] = Field(None, description="An optional text comment for the review.")


class ReviewCreate(ReviewBase):
    """
    Schema used for creating a new review.
    """
    pass


class ReviewResponse(ReviewBase):
    """
    Schema for returning review information from the API.
    Includes database-generated fields.
    """
    id: uuid.UUID
    review_date: datetime

    class Config:
        from_attributes = True

