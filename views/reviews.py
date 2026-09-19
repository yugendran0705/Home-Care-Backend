# /views/reviews.py

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from config.database import get_db
from utils.roleChecker import RoleChecker
from utils.logger import logger
from services.reviews import ReviewService
import models
from schemas.reviews import ReviewCreateRequest, ReviewUpdateRequest, ReviewResponse

router = APIRouter(
    prefix="/reviews",
    tags=["Reviews"]
)


def get_review_service(db=Depends(get_db)) -> ReviewService:
    return ReviewService(db)


# Role-based access dependencies
patient_dependency = Depends(RoleChecker(allowed_roles=["Patient"]))
# Reviews are readable by the booking's own patient and nurse, and by Admins;
# the per-booking ownership check lives in ReviewService.
review_reader_dependency = Depends(RoleChecker(allowed_roles=["Admin", "Patient", "Nurse"]))


@router.post(
    "/bookings/{booking_id}",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a review for a completed booking",
)
def create_review(
    booking_id: uuid.UUID,
    review_in: ReviewCreateRequest,
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
    except Exception:
        logger.exception("Unexpected error creating review for booking %s", booking_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the review.",
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
    except Exception:
        logger.exception("Error fetching reviews for user %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching reviews.",
        )


@router.get(
    "/one/{review_id}",
    response_model=ReviewResponse,
    summary="Get a specific review by ID (author, reviewed nurse, or Admin)",
)
def get_review_by_id(
    review_id: uuid.UUID,
    current_user: models.User = review_reader_dependency,
    service: ReviewService = Depends(get_review_service),
):
    """
    Retrieves a specific review, restricted to its author, the reviewed
    nurse, or an Admin.
    """
    try:
        return service.get_review(
            review_id=review_id,
            user_id=current_user.id,
            is_admin=current_user.user_type == "Admin",
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error fetching review %s", review_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching review.",
        )


@router.get(
    "/bookings/{booking_id}",
    response_model=ReviewResponse,
    summary="Get the review for a specific booking (its patient, nurse, or Admin)",
)
def get_review_by_booking(
    booking_id: uuid.UUID,
    current_user: models.User = review_reader_dependency,
    service: ReviewService = Depends(get_review_service),
):
    """
    Retrieves a booking's review, restricted to that booking's patient,
    nurse, or an Admin.
    """
    try:
        return service.get_review_by_booking(
            booking_id=booking_id,
            user_id=current_user.id,
            is_admin=current_user.user_type == "Admin",
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error fetching review for booking %s", booking_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching review.",
        )


@router.put(
    "/{review_id}",
    response_model=ReviewResponse,
    summary="Update the current user's review",
)
def update_review(
    review_id: uuid.UUID,
    review_in: ReviewUpdateRequest,
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
            updates=review_in.model_dump(exclude_unset=True),
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        logger.exception("Unexpected error updating review %s", review_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the review.",
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
    except Exception:
        logger.exception("Unexpected error deleting review %s", review_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the review.",
        )