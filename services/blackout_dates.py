# services/blackout_dates.py

import uuid
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models
from repositories.blackout_dates import BlackoutDateRepository
from schemas.blackout_dates import BlackoutDateCreate, BlackoutDateUpdate

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class BlackoutDateService:
    """
    Service layer for handling all business logic related to Blackout Dates.
    It orchestrates blackout creation and management.
    """

    def __init__(self, db: Session):
        self.db = db
        self.blackout_repo = BlackoutDateRepository(db)

    def create_blackout_date(
        self, nurse_id: uuid.UUID, blackout_data: BlackoutDateCreate
    ) -> models.BlackoutDate:
        """
        Creates a blackout date for a nurse.

        Args:
            nurse_id (uuid.UUID): Nurse ID.
            blackout_data (BlackoutDateCreate): Blackout date details.

        Returns:
            models.BlackoutDate: Newly created blackout date.
        """

        now = datetime.now()

        # Validate future dates
        if blackout_data.start_datetime < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start datetime must be valid, not in the past.",
            )

        if blackout_data.end_datetime < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End datetime must be valid, not in the past.",
            )

        # Validate date range
        if blackout_data.start_datetime >= blackout_data.end_datetime:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start datetime must be before end datetime.",
            )

        # Check overlapping blackout dates
        overlapping_blackouts = self.blackout_repo.find_overlapping(
            nurse_id=nurse_id,
            start_datetime=blackout_data.start_datetime,
            end_datetime=blackout_data.end_datetime,
        )

        if overlapping_blackouts:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This blackout period overlaps with an existing blackout date.",
            )

        try:
            new_blackout = self.blackout_repo.create(
                blackout_data={
                    "nurse_id": nurse_id,
                    "start_datetime": blackout_data.start_datetime,
                    "end_datetime": blackout_data.end_datetime,
                    "reason": blackout_data.reason,
                }
            )

            return new_blackout

        except Exception as e:
            self.db.rollback()

            logger.exception("Failed to create blackout date for nurse_id=%s", nurse_id)

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create blackout date",
            )

    def get_blackout_date(
        self, nurse_id: uuid.UUID, blackout_date_id: uuid.UUID
    ) -> models.BlackoutDate:
        """
        Retrieves a blackout date by its ID.

        Args:
            blackout_date_id (uuid.UUID): Blackout date ID.

        Returns:
            models.BlackoutDate: Blackout date ORM object.
        """

        logger.debug(f"Fetching blackout date {blackout_date_id} from database")
        blackout_date = self.blackout_repo.get_by_id(blackout_date_id=blackout_date_id)

        if not blackout_date or blackout_date.nurse_id != nurse_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blackout date not found or not authorized to view this blackout date.",
            )

        return blackout_date

    def get_nurse_blackout_dates(
        self, nurse_id: uuid.UUID
    ) -> list[models.BlackoutDate]:
        """
        Retrieves all blackout dates for a nurse.

        Args:
            nurse_id (uuid.UUID): Nurse ID.

        Returns:
            list[models.BlackoutDate]
        """
        logger.debug(f"Fetching blackout date for nurse {nurse_id} from database")
        blackout_dates = self.blackout_repo.get_by_nurse_id(nurse_id=nurse_id)

        return blackout_dates

    def update_blackout_date(
        self,
        nurse_id: uuid.UUID,
        blackout_date_id: uuid.UUID,
        updates: BlackoutDateUpdate,
    ) -> models.BlackoutDate:
        """
        Updates a blackout date.

        Args:
            blackout_date_id (uuid.UUID): Blackout date ID.
            updates (BlackoutDateUpdate): Fields to update.

        Returns:
            models.BlackoutDate
        """

        blackout_date = self.blackout_repo.get_by_id(blackout_date_id=blackout_date_id)

        if not blackout_date or blackout_date.nurse_id != nurse_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blackout date not found or not authorized to view this blackout date.",
            )

        update_data = updates.model_dump(exclude_unset=True)

        if not update_data:
            return blackout_date

        start_datetime = update_data.get("start_datetime", blackout_date.start_datetime)

        end_datetime = update_data.get("end_datetime", blackout_date.end_datetime)

        if start_datetime is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start datetime cannot be null.",
            )

        if end_datetime is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End datetime cannot be null.",
            )

        now = datetime.now()

        # Validate future dates
        if start_datetime < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start datetime must be valid, not in the past.",
            )

        if end_datetime < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End datetime must be valid, not in the past.",
            )

        if start_datetime >= end_datetime:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start datetime must be before end datetime.",
            )

        overlapping_blackouts = self.blackout_repo.find_overlapping(
            nurse_id=blackout_date.nurse_id,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            exclude_blackout_id=blackout_date.id,
        )

        if overlapping_blackouts:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This blackout period overlaps with an existing blackout date.",
            )

        try:

            updated_blackout = self.blackout_repo.update(
                blackout_date_id=blackout_date_id, updates=update_data
            )

            return updated_blackout

        except Exception:
            self.db.rollback()

            logger.exception(
                "Failed to update blackout date blackout_date_id=%s", blackout_date_id
            )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update blackout date",
            )

    def delete_blackout_date(
        self,
        nurse_id: uuid.UUID,
        blackout_date_id: uuid.UUID,
    ) -> bool:
        """
        Deletes a blackout date.
        """

        blackout_date = self.blackout_repo.get_by_id(blackout_date_id=blackout_date_id)

        if not blackout_date or blackout_date.nurse_id != nurse_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blackout date not found or not authorized to view this blackout date.",
            )

        self.blackout_repo.delete(blackout_date_id=blackout_date_id)

        return True
