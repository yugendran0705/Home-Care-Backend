# /views/blackout_dates.py

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from config.database import get_db
from utils.roleChecker import RoleChecker

from services.blackout_dates import BlackoutDateService

import models

from schemas.blackout_dates import (
    BlackoutDateCreate,
    BlackoutDateUpdate,
    BlackoutDateResponse
)

router = APIRouter(
    prefix="/blackout-dates",
    tags=["Blackout Dates"]
)


def get_blackout_date_service(
    db=Depends(get_db)
) -> BlackoutDateService:
    return BlackoutDateService(db)


nurse_dependency = Depends(RoleChecker(allowed_roles=["Admin", "Nurse"]))
admin_dependency = Depends(RoleChecker(allowed_roles=["Admin"]))


@router.post(
    "/",
    response_model=BlackoutDateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create blackout date"
)
def create_blackout_date(
    blackout_in: BlackoutDateCreate,
    current_user: models.User = nurse_dependency,
    service: BlackoutDateService = Depends(
        get_blackout_date_service
    )
):
    try:
        return service.create_blackout_date(
            nurse_id=current_user.id,
            blackout_data=blackout_in
        )

    except HTTPException as e:
        raise e

    except Exception as e:
        print(f"Error creating blackout date: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred."
        )


@router.get(
    "/me",
    response_model=List[BlackoutDateResponse],
    summary="Get all blackout dates for current nurse"
)
def get_my_blackout_dates(
    current_user: models.User = nurse_dependency,
    service: BlackoutDateService = Depends(
        get_blackout_date_service
    )
):
    try:
        return service.get_nurse_blackout_dates(
            nurse_id=current_user.id
        )

    except HTTPException as e:
        raise e

    except Exception as e:
        print(f"Error fetching blackout dates: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred."
        )


@router.get(
    "/one/{blackout_date_id}",
    response_model=BlackoutDateResponse,
    summary="Get blackout date by ID"
)
def get_blackout_date(
    blackout_date_id: uuid.UUID,
    current_user: models.User = nurse_dependency,
    service: BlackoutDateService = Depends(
        get_blackout_date_service
    )
):
    try:
        blackout_date = service.get_blackout_date(
            blackout_date_id=blackout_date_id
        )

        if blackout_date.nurse_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this blackout date."
            )

        return blackout_date

    except HTTPException as e:
        raise e

    except Exception as e:
        print(f"Error fetching blackout date: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred."
        )


@router.put(
    "/{blackout_date_id}",
    response_model=BlackoutDateResponse,
    summary="Update blackout date"
)
def update_blackout_date(
    blackout_date_id: uuid.UUID,
    blackout_update: BlackoutDateUpdate,
    current_user: models.User = nurse_dependency,
    service: BlackoutDateService = Depends(
        get_blackout_date_service
    )
):
    try:
        blackout_date = service.get_blackout_date(
            blackout_date_id=blackout_date_id
        )

        if blackout_date.nurse_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this blackout date."
            )

        return service.update_blackout_date(
            blackout_date_id=blackout_date_id,
            updates=blackout_update
        )

    except HTTPException as e:
        raise e

    except Exception as e:
        print(f"Error updating blackout date: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred."
        )


@router.delete(
    "/{blackout_date_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete blackout date"
)
def delete_blackout_date(
    blackout_date_id: uuid.UUID,
    current_user: models.User = nurse_dependency,
    service: BlackoutDateService = Depends(
        get_blackout_date_service
    )
):
    try:
        blackout_date = service.get_blackout_date(
            blackout_date_id=blackout_date_id
        )

        if blackout_date.nurse_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this blackout date."
            )

        service.delete_blackout_date(
            blackout_date_id=blackout_date_id
        )

        return None

    except HTTPException as e:
        raise e

    except Exception as e:
        print(f"Error deleting blackout date: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred."
        )