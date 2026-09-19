# /repositories/reviews.py

import uuid
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import select, func

import models
from schemas.reviews import ReviewCreate


class ReviewRepository:
    """
    Repository for handling all direct database operations for the Review model.
    """

    def __init__(self, db: Session):
        """
        Initializes the repository with a database session.
        """
        self.db = db

    def create(self, *, review_in: ReviewCreate) -> models.Review:
        """
        Adds a new review and flushes so its id is populated, without
        committing - the service commits the review and the nurse's
        recomputed average_rating together in one transaction.
        """
        db_review = models.Review(**review_in.model_dump())

        self.db.add(db_review)
        self.db.flush()
        return db_review

    def get_by_id(self, *, review_id: uuid.UUID) -> Optional[models.Review]:
        """
        Retrieves a review by its primary key.

        Args:
            review_id (uuid.UUID): The ID of the review to retrieve.

        Returns:
            Optional[models.Review]: The Review object if found, otherwise None.
        """
        return self.db.get(models.Review, review_id)

    def get_by_booking_id(self, *, booking_id: uuid.UUID) -> Optional[models.Review]:
        """
        Retrieves a review by the associated booking ID.

        Args:
            booking_id (uuid.UUID): The ID of the booking.

        Returns:
            Optional[models.Review]: The Review object if found, otherwise None.
        """
        statement = select(models.Review).where(models.Review.booking_id == booking_id)
        return self.db.execute(statement).scalar_one_or_none()

    def get_for_patient(self, *, patient_id: uuid.UUID) -> List[models.Review]:
        """
        Retrieves all reviews written by a specific patient.

        Args:
            patient_id (uuid.UUID): The patient's ID.

        Returns:
            List[models.Review]: A list of reviews written by the patient.
        """
        statement = select(models.Review).where(models.Review.patient_id == patient_id)
        return self.db.execute(statement).scalars().all()

    def delete(self, *, review_id: uuid.UUID) -> Optional[models.Review]:
        """
        Deletes a review and flushes without committing - the service commits
        the deletion and the nurse's recomputed average_rating together.
        """
        db_review = self.get_by_id(review_id=review_id)
        if not db_review:
            return None

        self.db.delete(db_review)
        self.db.flush()
        return db_review

    def average_rating_for_nurse(self, *, nurse_id: uuid.UUID):
        """
        Returns AVG(rating) over all of a nurse's reviews as a Decimal, or None
        when the nurse has no reviews.
        """
        return (
            self.db.query(func.avg(models.Review.rating))
            .filter(models.Review.nurse_id == nurse_id)
            .scalar()
        )
