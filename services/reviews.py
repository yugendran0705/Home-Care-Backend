# services/reviews.py

import uuid
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

import models
from repositories.reviews import ReviewRepository
from repositories.bookings import BookingRepository
from services.notifications import NotificationService
from schemas.reviews import ReviewCreate, ReviewResponse
from utils.logger import logger


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
        self.notification_service = NotificationService(db)

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

        # A Daily_Shift parent is a billing wrapper; each shift is its own
        # visit and is reviewed on its own (the parent can still be Completed
        # once all its shifts are).
        if booking.is_parent_booking:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This booking is a multi-shift wrapper; review each shift on its own.",
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
            self._recompute_nurse_rating(nurse_id=booking.nurse_id)
            self.db.commit()
        except IntegrityError:
            # The unique constraint on booking_id is the race-safe backstop for
            # the check above: a concurrent create that slipped past it lands
            # here, and it's the same "already reviewed" condition, not a 500.
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A review already exists for this booking.",
            )
        except Exception:
            self.db.rollback()
            logger.exception("Failed to create review for booking %s", booking_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create review.",
            )

        self.db.refresh(review)
        response = ReviewResponse.model_validate(review)
        # After the commit and snapshot: best-effort, can't affect the review.
        self.notification_service.review_received(review, booking)
        return response

    def _recompute_nurse_rating(self, *, nurse_id: uuid.UUID) -> None:
        """
        Recomputes and writes the nurse's average_rating from all their
        reviews. No commit - the caller commits this together with the review
        write so the two never drift apart. Resets to 0 when no reviews remain.
        """
        # The session is autoflush=False, so flush any pending review change
        # (e.g. an updated rating) before the aggregate query reads the DB -
        # otherwise the AVG is computed against stale rows.
        self.db.flush()
        average = self.review_repo.average_rating_for_nurse(nurse_id=nurse_id)
        nurse = self.db.get(models.Nurse, nurse_id)
        if nurse is not None:
            nurse.average_rating = round(average, 2) if average is not None else 0

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    # A review is visible only to the patient who wrote it, the nurse it's
    # about, and Admins. Anyone else gets the same 404 as a missing review, so
    # these endpoints can't be used to probe which bookings/reviews exist.
    def get_review(
        self, *, review_id: uuid.UUID, user_id: uuid.UUID, is_admin: bool = False
    ) -> ReviewResponse:
        review = self.review_repo.get_by_id(review_id=review_id)
        if not review or not (
            is_admin or user_id in (review.patient_id, review.nurse_id)
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found.",
            )
        return ReviewResponse.model_validate(review)

    def get_review_by_booking(
        self, *, booking_id: uuid.UUID, user_id: uuid.UUID, is_admin: bool = False
    ) -> ReviewResponse:
        booking = self.booking_repo.get_by_id(booking_id=booking_id)
        if not booking or not (
            is_admin or user_id in (booking.patient_id, booking.nurse_id)
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No review found for this booking.",
            )
        review = self.review_repo.get_by_booking_id(booking_id=booking_id)
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No review found for this booking.",
            )
        return ReviewResponse.model_validate(review)

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
        updates: dict,
    ) -> ReviewResponse:
        """
        Only the original reviewer can edit their review. `updates` carries
        only the fields the client actually sent (the view builds it with
        exclude_unset), so a caller can change just the rating, just the
        comment, or explicitly clear the comment by sending it as null.
        Rating bounds are already enforced by the request schema.
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

        # rating is NOT NULL, so a sent-but-null rating is ignored; comment is
        # nullable, so sending it as null is an explicit clear.
        rating_changed = updates.get("rating") is not None
        if rating_changed:
            review.rating = updates["rating"]

        if "comment" in updates:
            review.comment = updates["comment"]

        try:
            if rating_changed:
                self._recompute_nurse_rating(nurse_id=review.nurse_id)
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("Failed to update review %s", review_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update review.",
            )

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

        # Snapshot before deletion - the ORM instance's attributes aren't
        # safely readable once the row is gone and the transaction commits.
        nurse_id = review.nurse_id
        response = ReviewResponse.model_validate(review)
        try:
            self.review_repo.delete(review_id=review_id)
            self._recompute_nurse_rating(nurse_id=nurse_id)
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("Failed to delete review %s", review_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete review.",
            )

        return response