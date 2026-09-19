# /schemas/review.py

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


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
    Full review payload assembled server-side before persistence. patient_id
    and nurse_id are filled in from the authenticated user and the booking, not
    from the client - see ReviewCreateRequest for what the client actually sends.
    """
    pass


class ReviewCreateRequest(BaseModel):
    """
    The request body for creating a review. booking_id is taken from the URL,
    patient_id from the auth token, and nurse_id from the booking - so the
    client only supplies the rating and an optional comment.
    """
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    comment: Optional[str] = Field(None, description="An optional text comment for the review.")


class ReviewUpdateRequest(BaseModel):
    """
    The request body for updating a review. Both fields are optional so the
    client can update just the rating, just the comment, or both.
    """
    rating: Optional[int] = Field(None, ge=1, le=5, description="Rating from 1 to 5")
    comment: Optional[str] = Field(None, description="An optional text comment for the review.")


class ReviewResponse(ReviewBase):
    """
    Schema for returning review information from the API.
    Includes database-generated fields.
    """
    id: uuid.UUID
    review_date: datetime

    class Config:
        from_attributes = True

