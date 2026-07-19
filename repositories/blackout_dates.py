# /repositories/blackout_dates.py

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_

import models


class BlackoutDateRepository:
    """
    Repository for handling all direct database operations
    for the BlackoutDate model.
    """

    def __init__(self, db: Session):
        self.db = db

    def create(self, *, blackout_data: Dict[str, Any]) -> models.BlackoutDate:
        db_blackout = models.BlackoutDate(**blackout_data)

        self.db.add(db_blackout)
        self.db.commit()
        self.db.refresh(db_blackout)

        return db_blackout

    def get_by_id(
        self, *, blackout_date_id: uuid.UUID
    ) -> Optional[models.BlackoutDate]:

        statement = select(models.BlackoutDate).where(
            models.BlackoutDate.id == blackout_date_id
        )

        return self.db.execute(statement).scalar_one_or_none()

    def get_by_nurse_id(self, *, nurse_id: uuid.UUID) -> List[models.BlackoutDate]:

        statement = (
            select(models.BlackoutDate)
            .where(models.BlackoutDate.nurse_id == nurse_id)
            .order_by(models.BlackoutDate.start_datetime)
        )

        return self.db.execute(statement).scalars().all()

    def update(
        self, *, blackout_date_id: uuid.UUID, updates: Dict[str, Any]
    ) -> Optional[models.BlackoutDate]:

        db_blackout = self.get_by_id(blackout_date_id=blackout_date_id)

        if not db_blackout:
            return None

        for key, value in updates.items():
            setattr(db_blackout, key, value)

        self.db.add(db_blackout)
        self.db.commit()
        self.db.refresh(db_blackout)

        return db_blackout

    def delete(self, *, blackout_date_id: uuid.UUID) -> Optional[models.BlackoutDate]:

        db_blackout = self.get_by_id(blackout_date_id=blackout_date_id)

        if not db_blackout:
            return None

        self.db.delete(db_blackout)
        self.db.commit()

        return db_blackout

    def find_overlapping(
        self,
        *,
        nurse_id: uuid.UUID,
        start_datetime,
        end_datetime,
        exclude_blackout_id: Optional[uuid.UUID] = None
    ) -> List[models.BlackoutDate]:

        statement = select(models.BlackoutDate).where(
            and_(
                models.BlackoutDate.nurse_id == nurse_id,
                models.BlackoutDate.start_datetime < end_datetime,
                models.BlackoutDate.end_datetime > start_datetime,
            )
        )

        if exclude_blackout_id:
            statement = statement.where(models.BlackoutDate.id != exclude_blackout_id)

        return self.db.execute(statement).scalars().all()

    def has_overlap(
        self, *, nurse_id: uuid.UUID, windows: List[Tuple[datetime, datetime]]
    ) -> bool:
        """
        True if the nurse has ANY blackout overlapping ANY of the given
        (start, end) windows - one and_() condition per window, OR'd together,
        same style as BookingRepository.find_conflicting.
        """
        if not windows:
            return False

        window_filters = [
            and_(
                models.BlackoutDate.start_datetime < end,
                models.BlackoutDate.end_datetime > start,
            )
            for start, end in windows
        ]

        conflict = (
            self.db.query(models.BlackoutDate.id)
            .filter(models.BlackoutDate.nurse_id == nurse_id, or_(*window_filters))
            .first()
        )
        return conflict is not None
