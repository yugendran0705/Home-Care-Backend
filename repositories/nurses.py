# /repositories/nurses.py

import uuid
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, func, and_, or_
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

# Adjust the import path based on your project structure
import models


class NurseRepository:
    """
    Repository for handling all direct database operations for the Nurse model.
    """

    def __init__(self, db: Session):
        """
        Initializes the repository with a database session.

        Args:
            db (Session): The SQLAlchemy database session.
        """
        self.db = db

    def create(self, *, nurse_data: Dict[str, Any]) -> models.Nurse:
        """
        Creates a new nurse profile record.
        Expects a dictionary of nurse data, including the user_id as 'id'.

        Args:
            nurse_data (Dict[str, Any]): Dictionary containing the nurse's profile information.

        Returns:
            models.Nurse: The newly created Nurse ORM object.
        """
        db_nurse = models.Nurse(**nurse_data)
        self.db.add(db_nurse)
        self.db.commit()
        self.db.refresh(db_nurse)
        return db_nurse

    def get_by_id(self, *, nurse_id: uuid.UUID) -> Optional[models.Nurse]:
        """
        Retrieves a nurse by their primary key (which is also the user_id).

        Args:
            nurse_id (uuid.UUID): The ID of the nurse to retrieve.

        Returns:
            Optional[models.Nurse]: The Nurse object if found, otherwise None.
        """
        statement = (
            select(models.Nurse)
            .where(models.Nurse.id == nurse_id)
            .options(joinedload(models.Nurse.user).selectinload(models.User.addresses))
        )
        return self.db.execute(statement).unique().scalar_one_or_none()

    def get_by_license_number(self, *, license_number: str) -> Optional[models.Nurse]:
        """
        Retrieves a nurse by their unique license number.

        Args:
            license_number (str): The nurse's license number.

        Returns:
            Optional[models.Nurse]: The Nurse object if found, otherwise None.
        """
        statement = select(models.Nurse).where(
            models.Nurse.license_number == license_number
        )
        return self.db.execute(statement).scalar_one_or_none()

    def update(
        self, *, nurse_id: uuid.UUID, updates: Dict[str, Any]
    ) -> Optional[models.Nurse]:
        """
        Updates an existing nurse's profile.

        Args:
            nurse_id (uuid.UUID): The ID of the nurse to update.
            updates (Dict[str, Any]): A dictionary of fields to update.

        Returns:
            Optional[models.Nurse]: The updated Nurse object, or None if not found.
        """
        db_nurse = self.get_by_id(nurse_id=nurse_id)
        if not db_nurse:
            return None

        for key, value in updates.items():
            setattr(db_nurse, key, value)

        self.db.add(db_nurse)
        self.db.commit()
        self.db.refresh(db_nurse)
        return db_nurse

    def list_all(self, *, skip: int = 0, limit: int = 100) -> List[models.Nurse]:
        """
        Retrieves a paginated list of all nurse records.

        Args:
            skip (int): The number of records to skip.
            limit (int): The maximum number of records to return.

        Returns:
            List[models.Nurse]: A list of Nurse objects.
        """
        statement = (
            select(models.Nurse)
            .offset(skip)
            .limit(limit)
            .options(joinedload(models.Nurse.user).selectinload(models.User.addresses))
        )
        return self.db.execute(statement).unique().scalars().all()

    def delete(self, *, nurse_id: uuid.UUID) -> Optional[models.Nurse]:
        """
        Deletes a nurse record from the database.
        Note: In a real application, this would likely be a soft delete
        handled by deactivating the associated User account in the service layer.

        Args:
            nurse_id (uuid.UUID): The ID of the nurse to delete.

        Returns:
            Optional[models.Nurse]: The deleted Nurse object, or None if not found.
        """
        db_nurse = self.get_by_id(nurse_id=nurse_id)
        if not db_nurse:
            return None

        self.db.delete(db_nurse)
        self.db.commit()
        return db_nurse

    def search_available_nurses(
        self,
        service_id: uuid.UUID,
        patient_lat: float,
        patient_lon: float,
        requested_start_time: datetime,
        requested_end_time: datetime,
        search_radius_meters: int = 8000,
    ) -> List[models.Nurse]:
        """
        Finds available nurses for a given service, location, and time window.

        For Daily_Shift services:
            requested_start_time = start of the first shift
            requested_end_time   = end of the last shift (full booking period end)
        For Continuous services:
            requested_start_time = booking start
            requested_end_time   = booking end
        """

        # Fix 1: query the service directly — NurseRepository has no service_repo
        service = self.db.get(models.NursingService, service_id)
        if not service:
            raise ValueError("Service not found.")

        travel_buffer = timedelta(minutes=30)
        target_point = func.ST_SetSRID(
            func.ST_MakePoint(patient_lon, patient_lat), 4326
        )

        # --- BASE QUERY ---
        # Fix 2: NurseService → NurseAssociatedService (correct model name)
        # Fix 3: Nurse has no address_id; location lives on Address linked via User
        query = (
            self.db.query(models.Nurse)
            .join(
                models.NurseAssociatedService,
                models.Nurse.id == models.NurseAssociatedService.nurse_id,
            )
            .join(models.User, models.Nurse.id == models.User.id)
            .join(models.Address, models.User.id == models.Address.user_id)
            .filter(
                models.Address.is_primary == True,
                models.NurseAssociatedService.service_id == service_id,
                func.ST_DWithin(
                    models.Address.location, target_point, search_radius_meters
                ),
                models.Nurse.is_verified == True,
            )
        )

        # --- SCHEDULE-TYPE FILTERS ---

        if service.schedule_type == "Daily_Shift":
            if not service.shift_duration_hours:
                 raise ValueError("Daily_Shift services must have shift_duration_hours defined.")
            start_date = requested_start_time.date()
            end_date = requested_end_time.date()
            shift_windows = []
            current_date = start_date

            def _time_only(dt: datetime):
                return dt.timetz() if dt.tzinfo else dt.time()

            while current_date <= end_date:
                shift_start = datetime.combine(
                    current_date, _time_only(requested_start_time)
                )
                shift_end = shift_start + timedelta(hours=service.shift_duration_hours)
                shift_windows.append((shift_start, shift_end))
                current_date += timedelta(days=1)

            blackout_filters = [
                and_(
                    models.BlackoutDate.start_datetime < shift_end,
                    models.BlackoutDate.end_datetime > shift_start,
                )
                for shift_start, shift_end in shift_windows
            ]
            booking_filters = [
                and_(
                    models.Booking.scheduled_start_time < shift_end + travel_buffer,
                    models.Booking.scheduled_end_time > shift_start - travel_buffer,
                )
                for shift_start, shift_end in shift_windows
            ]

            overlapping_blackouts = (
                self.db.query(models.BlackoutDate.nurse_id)
                .filter(or_(*blackout_filters))
                .subquery()
            )

            # Only child bookings carry real time slots; parent bookings are billing wrappers
            overlapping_bookings = (
                self.db.query(models.Booking.nurse_id)
                .filter(
                    models.Booking.booking_status == "Confirmed",
                    models.Booking.payment_status == "Paid",
                    models.Booking.is_parent_booking == False,
                    or_(*booking_filters),
                )
                .subquery()
            )

            query = query.filter(
                ~models.Nurse.id.in_(select(overlapping_blackouts.c.nurse_id)),
                ~models.Nurse.id.in_(select(overlapping_bookings.c.nurse_id)),
            )

            # The shift repeats at the same clock time each day.
            # Compute the daily time window from the first shift's start + shift_duration_hours.
            req_start_time_only = (
                requested_start_time.timetz()
                if requested_start_time.tzinfo
                else requested_start_time.time()
            )
            shift_end = requested_start_time + timedelta(
                hours=service.shift_duration_hours
            )
            req_end_time_only = (
                shift_end.timetz() if shift_end.tzinfo else shift_end.time()
            )

            # Fix 4: collect ALL distinct weekdays across the full booking date range.
            # A nurse working Mon–Fri must be excluded from a 14-day booking that includes weekends.
            total_days = (end_date - start_date).days + 1
            required_weekdays = list(
                {(start_date + timedelta(days=i)).weekday() for i in range(total_days)}
            )

            # Count how many of the required weekdays each nurse actually covers.
            # A nurse is eligible only when that count equals the number of required weekdays.
            covered_days_subq = (
                self.db.query(
                    models.WorkingHours.nurse_id,
                    func.count(func.distinct(models.WorkingHours.day_of_week)).label(
                        "covered"
                    ),
                )
                .filter(
                    models.WorkingHours.is_active == True,
                    models.WorkingHours.day_of_week.in_(required_weekdays),
                    models.WorkingHours.start_time <= req_start_time_only,
                    models.WorkingHours.end_time >= req_end_time_only,
                )
                .group_by(models.WorkingHours.nurse_id)
                .subquery()
            )

            query = query.join(
                covered_days_subq, models.Nurse.id == covered_days_subq.c.nurse_id
            ).filter(covered_days_subq.c.covered >= len(required_weekdays))

        elif service.schedule_type == "Continuous":
            buffered_start = requested_start_time - travel_buffer
            buffered_end = requested_end_time + travel_buffer

            overlapping_blackouts = (
                self.db.query(models.BlackoutDate.nurse_id)
                .filter(
                    models.BlackoutDate.start_datetime < requested_end_time,
                    models.BlackoutDate.end_datetime > requested_start_time,
                )
                .subquery()
            )

            # Only child bookings carry real time slots; parent bookings are billing wrappers
            overlapping_bookings = (
                self.db.query(models.Booking.nurse_id)
                .filter(
                    models.Booking.booking_status == "Confirmed",
                    models.Booking.payment_status == "Paid",
                    models.Booking.is_parent_booking == False,
                    models.Booking.scheduled_start_time < buffered_end,
                    models.Booking.scheduled_end_time > buffered_start,
                )
                .subquery()
            )

            # No working-hours check for live-in/24-7 care, but the nurse must have
            # opted in for continuous assignments.
            query = query.filter(
                models.Nurse.continuous_care_available == True,
                ~models.Nurse.id.in_(select(overlapping_blackouts.c.nurse_id)),
                ~models.Nurse.id.in_(select(overlapping_bookings.c.nurse_id)),
            )

        return query.all()
