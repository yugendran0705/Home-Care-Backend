# /views/reviews.py

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from config.database import get_db
from utils.roleChecker import RoleChecker
from services.reviews import ReviewService
import models
from schemas.reviews import ReviewCreate, ReviewResponse

router = APIRouter(
    prefix="/reviews",
    tags=["Reviews"]
)


def get_review_service(db=Depends(get_db)) -> ReviewService:
    return ReviewService(db)


# Role-based access dependencies
patient_dependency = Depends(RoleChecker(allowed_roles=["Patient"]))
user_dependency = Depends(RoleChecker(allowed_roles=["Admin", "Patient", "Nurse"]))
admin_dependency = Depends(RoleChecker(allowed_roles=["Admin"]))


@router.post(
    "/bookings/{booking_id}",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a review for a completed booking",
)
def create_review(
    booking_id: uuid.UUID,
    review_in: ReviewCreate,
    current_user: models.User = patient_dependency,
    service: ReviewService = Depends(get_review_service),
):
    """
    Creates a review for the given booking. patient_id and nurse_id are
    never taken from the request body - patient_id comes from the
    authenticated user, and nurse_id is derived server-side from the
    booking itself.
    """
    try:
        return service.create_review(
            booking_id=booking_id,
            patient_id=current_user.id,
            rating=review_in.rating,
            comment=review_in.comment,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        print(f"Unexpected error creating review for booking {booking_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )


@router.get(
    "/me",
    response_model=List[ReviewResponse],
    summary="Get all reviews written by the current user",
)
def get_my_reviews(
    current_user: models.User = patient_dependency,
    service: ReviewService = Depends(get_review_service),
):
    """
    Retrieves all reviews written by the currently authenticated patient.
    """
    try:
        return service.get_reviews_by_patient(patient_id=current_user.id)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching reviews for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching reviews.",
        )


@router.get(
    "/one/{review_id}",
    response_model=ReviewResponse,
    summary="Get a specific review by ID (owner-restricted)",
)
def get_review_by_id(
    review_id: uuid.UUID,
    current_user: models.User = user_dependency,
    service: ReviewService = Depends(get_review_service),
):
    """
    Retrieves a specific review, restricted to its author, the reviewed
    nurse, or an Admin.
    """
    try:
        review = service.get_review(review_id=review_id)
        is_owner = review.patient_id == current_user.id
        is_reviewed_nurse = review.nurse_id == current_user.id
        is_admin = current_user.role == "Admin"
        if not (is_owner or is_reviewed_nurse or is_admin):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found or not authorized to view this review.",
            )
        return review
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching review {review_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching review.",
        )


@router.get(
    "/bookings/{booking_id}",
    response_model=ReviewResponse,
    summary="Get the review for a specific booking",
)
def get_review_by_booking(
    booking_id: uuid.UUID,
    current_user: models.User = user_dependency,
    service: ReviewService = Depends(get_review_service),
):
    try:
        return service.get_review_by_booking(booking_id=booking_id)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching review for booking {booking_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching review.",
        )


@router.get(
    "/nurses/{nurse_id}",
    response_model=List[ReviewResponse],
    summary="Get all reviews for a specific nurse (public-facing)",
)
def get_reviews_for_nurse(
    nurse_id: uuid.UUID,
    service: ReviewService = Depends(get_review_service),
):
    """
    A nurse's reviews are public-facing (patients browsing nurses need to
    see them), so no role restriction here - adjust if that's not
    actually the intent.
    """
    try:
        return service.get_reviews_for_nurse(nurse_id=nurse_id)
    except Exception as e:
        print(f"Error fetching reviews for nurse {nurse_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching reviews.",
        )


@router.patch(
    "/{review_id}",
    response_model=ReviewResponse,
    summary="Update the current user's review",
)
def update_review(
    review_id: uuid.UUID,
    rating: int | None = None,
    comment: str | None = None,
    current_user: models.User = patient_dependency,
    service: ReviewService = Depends(get_review_service),
):
    """
    Updates a review, ensuring it belongs to the authenticated user.
    """
    try:
        return service.update_review(
            review_id=review_id,
            patient_id=current_user.id,
            rating=rating,
            comment=comment,
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        print(f"Unexpected error updating review {review_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )


@router.delete(
    "/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete the current user's review",
)
def delete_review(
    review_id: uuid.UUID,
    current_user: models.User = patient_dependency,
    service: ReviewService = Depends(get_review_service),
):
    """
    Deletes a review, ensuring it belongs to the authenticated user.
    """
    try:
        service.delete_review(review_id=review_id, patient_id=current_user.id)
        return None
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        print(f"Unexpected error deleting review: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )