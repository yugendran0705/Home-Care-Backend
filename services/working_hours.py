import models

import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import List, Dict

from repositories.working_hours import WorkingHoursRepository
from schemas.working_hours import WorkingHoursCreate, WorkingHoursUpdate


class WorkingHoursService:
    """
    Service layer for nurse working hours business logic.
    """

    def __init__(self, db: Session):
        self.working_hours_repo = WorkingHoursRepository(db)

    def create_working_hours(
        self, *, nurse_id: uuid.UUID, working_hours_in: WorkingHoursCreate
    ) -> models.WorkingHours:
        """
        Creates a working hours record for a specific nurse.

        """
        overlapping_working_hours = self.working_hours_repo.find_overlapping(
            nurse_id=nurse_id,
            day_of_week=working_hours_in.day_of_week,
            start_time=working_hours_in.start_time,
            end_time=working_hours_in.end_time,
        )

        if overlapping_working_hours:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This working hours overlaps with an existing working hours record",
            )

        working_hours = working_hours_in.model_dump()
        return self.working_hours_repo.create(
            nurse_id=nurse_id, working_hours_in=working_hours
        )

    def _validate_no_internal_overlaps(
        self, working_hours_items: List[WorkingHoursCreate]
    ) -> None:
        """
        Ensure the provided list of working hours do not overlap each other.
        Raises HTTPException(409) on overlap.
        """
        # Assume all items are already `WorkingHoursCreate` instances
        

        # Group by day_of_week and check overlaps by sorting by start_time
        groups: Dict[int, List[WorkingHoursCreate]] = {}
        for item in working_hours_items:
            groups.setdefault(item.day_of_week, []).append(item)

        for day, items in groups.items():
            items.sort(key=lambda x: x.start_time)
            for i in range(1, len(items)):
                prev = items[i - 1]
                curr = items[i]
                # Overlap if previous end_time > current start_time
                if prev.end_time > curr.start_time:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Provided working hours list contains overlapping "
                            f"slots for day_of_week={day}: {prev.start_time}-{prev.end_time} "
                            f"and {curr.start_time}-{curr.end_time}"
                        ),
                    )

    def _validate_no_database_overlaps(
        self, *, nurse_id: uuid.UUID, working_hours_items: List[WorkingHoursCreate]
    ) -> None:
        """
        Ensure the provided working hours list does not overlap existing
        working hours already stored for the nurse.
        """
        for item in working_hours_items:
            overlapping_working_hours = self.working_hours_repo.find_overlapping(
                nurse_id=nurse_id,
                day_of_week=item.day_of_week,
                start_time=item.start_time,
                end_time=item.end_time,
            )
            if overlapping_working_hours:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Provided working hours list contains a slot that overlaps "
                        f"an existing record for day_of_week={item.day_of_week}: "
                        f"{item.start_time}-{item.end_time} overlaps {overlapping_working_hours.start_time}-{overlapping_working_hours.end_time}"
                    ),
                )

    def bulk_create_working_hours(
        self, *, nurse_id: uuid.UUID, working_hours_data: List[WorkingHoursCreate]
    ) -> List[models.WorkingHours]:
        """
        Creates multiple working hours records.

        """
        # First validate there are no overlaps inside the provided list
        self._validate_no_internal_overlaps(working_hours_data)
        self._validate_no_database_overlaps(
            nurse_id=nurse_id,
            working_hours_items=working_hours_data,
        )

        working_hours_payloads = [item.model_dump() for item in working_hours_data]
        return self.working_hours_repo.bulk_create(
            nurse_id=nurse_id, working_hours_data=working_hours_payloads
        )

    def get_working_hours_by_id(
        self, *, working_hours_id: uuid.UUID
    ) -> models.WorkingHours:
        """
        Retrieves a working hours record by its ID.

        Raises:
            HTTPException: If the record cannot be found.
        """
        working_hours = self.working_hours_repo.get_by_id(
            working_hours_id=working_hours_id
        )

        if not working_hours:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Working Hours not found",
            )

        return working_hours

    def get_working_hours_for_nurse(
        self, *, nurse_id: uuid.UUID
    ) -> List[models.WorkingHours]:
        """
        Retrieves all working hours records associated with a nurse.
        """
        return self.working_hours_repo.get_for_nurse(nurse_id=nurse_id)

    def update_working_hours(
        self, *, working_hours_id: uuid.UUID, updates: WorkingHoursUpdate
    ) -> models.WorkingHours:
        """
        Updates an existing working hours record.

        Raises:
            HTTPException: If the record does not exist, if the updated time
                range is invalid, or if the new range overlaps with another slot.
        """
        db_working_hours = self.working_hours_repo.get_by_id(
            working_hours_id=working_hours_id
        )

        if not db_working_hours:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Working Hours not found",
            )

        update_data = updates.model_dump(exclude_unset=True)
        if not update_data:
            return db_working_hours

        effective_day_of_week = update_data.get(
            "day_of_week", db_working_hours.day_of_week
        )
        effective_start_time = update_data.get(
            "start_time", db_working_hours.start_time
        )
        effective_end_time = update_data.get(
            "end_time", db_working_hours.end_time
        )

        if effective_start_time and effective_end_time and effective_end_time <= effective_start_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="End time must be after start time",
            )

        overlapping_working_hours = self.working_hours_repo.find_overlapping(
            nurse_id=db_working_hours.nurse_id,
            day_of_week=effective_day_of_week,
            start_time=effective_start_time,
            end_time=effective_end_time,
            exclude_working_hours_id=working_hours_id,
        )
        if overlapping_working_hours:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Updated working hours overlaps with an existing record",
            )

        return self.working_hours_repo.update(
            working_hours_id=working_hours_id, updates=update_data
        )

    def delete_working_hours(
        self, *, working_hours_id: uuid.UUID
    ) -> models.WorkingHours:
        """
        Deletes a working hours record by ID.

        Raises:
            HTTPException: If the record is not found.
        """
        working_hours = self.working_hours_repo.get_by_id(
            working_hours_id=working_hours_id
        )
        if not working_hours:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Working Hours not found",
            )

        return self.working_hours_repo.delete(working_hours_id=working_hours_id)
        
    