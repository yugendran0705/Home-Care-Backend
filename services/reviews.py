# services/reviews.py

import uuid
import logging
from typing import List

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

import models
from repositories.reviews import ReviewRepository
from repositories.bookings import BookingRepository
from schemas.reviews import ReviewCreate, ReviewResponse


class ReviewService:
    """
    Service layer for review business logic: booking-completion checks,
    ownership enforcement, and one-review-per-booking invariant. The
    repository stays a thin DB layer; all the "should this be allowed"
    decisions live here.
    """

    def __init__(self, db: Session):
        self.db = db
        self.review_repo = ReviewRepository(db)
        self.booking_repo = BookingRepository(db)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------
    def create_review(
        self,
        *,
        booking_id: uuid.UUID,
        patient_id: uuid.UUID,
        rating: int,
        comment: str | None = None,
    ) -> ReviewResponse:
        """
        Creates a review for a completed booking. patient_id here should
        come from the authenticated user (e.g. current_user.id), never
        from client-supplied review data - this prevents a patient from
        writing a review "as" someone else.
        """
        booking = self.booking_repo.get_by_id(booking_id=booking_id)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found.",
            )

        # Ownership: only the patient who made the booking can review it.
        if booking.patient_id != patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only review your own bookings.",
            )

        # Only allow reviewing a booking that actually happened.
        if booking.booking_status != "Completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot review a booking with status '{booking.booking_status}'. "
                       "Only completed bookings can be reviewed.",
            )

        # One review per booking - check before insert. A unique DB
        # constraint on booking_id should also exist as a race-safe backstop.
        existing = self.review_repo.get_by_booking_id(booking_id=booking_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A review already exists for this booking.",
            )

        # nurse_id is derived from the booking, never trusted from the client.
        review_in = ReviewCreate(
            booking_id=booking_id,
            patient_id=patient_id,
            nurse_id=booking.nurse_id,
            rating=rating,
            comment=comment,
        )

        try:
            review = self.review_repo.create(review_in=review_in)
        except Exception as e:
            logger.error(f"Failed to create review for booking {booking_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create review.",
            )

        return ReviewResponse.model_validate(review)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    def get_review(self, *, review_id: uuid.UUID) -> ReviewResponse:
        review = self.review_repo.get_by_id(review_id=review_id)
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found.",
            )
        return ReviewResponse.model_validate(review)

    def get_review_by_booking(self, *, booking_id: uuid.UUID) -> ReviewResponse:
        review = self.review_repo.get_by_booking_id(booking_id=booking_id)
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No review found for this booking.",
            )
        return ReviewResponse.model_validate(review)

    def get_reviews_for_nurse(self, *, nurse_id: uuid.UUID) -> List[ReviewResponse]:
        reviews = self.review_repo.get_for_nurse(nurse_id=nurse_id)
        return [ReviewResponse.model_validate(r) for r in reviews]

    def get_reviews_by_patient(self, *, patient_id: uuid.UUID) -> List[ReviewResponse]:
        reviews = self.review_repo.get_for_patient(patient_id=patient_id)
        return [ReviewResponse.model_validate(r) for r in reviews]

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------
    def update_review(
        self,
        *,
        review_id: uuid.UUID,
        patient_id: uuid.UUID,
        rating: int | None = None,
        comment: str | None = None,
    ) -> ReviewResponse:
        """
        Only the original reviewer can edit their review. rating/comment
        are optional so a caller can update just one field.
        """
        review = self.review_repo.get_by_id(review_id=review_id)
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found.",
            )

        if review.patient_id != patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only edit your own reviews.",
            )

        if rating is not None:
            if not (1 <= rating <= 5):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Rating must be between 1 and 5.",
                )
            review.rating = rating

        if comment is not None:
            review.comment = comment

        self.db.commit()
        self.db.refresh(review)
        return ReviewResponse.model_validate(review)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------
    def delete_review(self, *, review_id: uuid.UUID, patient_id: uuid.UUID) -> ReviewResponse:
        review = self.review_repo.get_by_id(review_id=review_id)
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found.",
            )

        if review.patient_id != patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own reviews.",
            )

        deleted = self.review_repo.delete(review_id=review_id)
        return ReviewResponse.model_validate(deleted)