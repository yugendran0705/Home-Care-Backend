# /repositories/nursing_services.py

import uuid
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta
import models
from schemas.nursing_services import NursingServiceCreate  # Assumes you will create this schema


class NursingServiceRepository:
    """
    Repository for handling all direct database operations for the Service model.
    """

    def __init__(self, db: Session):
        """
        Initializes the repository with a database session.

        Args:
            db (Session): The SQLAlchemy database session.
        """
        self.db = db

    def create(self, *, service_in: NursingServiceCreate) -> models.NursingService:
        """
        Creates a new service that can be offered by nurses.

        Args:
            service_in (ServiceCreate): A Pydantic schema with the new service data.

        Returns:
            models.NursingService: The newly created NursingService ORM object.
        """
        db_service = models.NursingService(**service_in.model_dump())

        self.db.add(db_service)
        self.db.commit()
        self.db.refresh(db_service)
        return db_service

    def get_by_id(self, *, service_id: uuid.UUID) -> Optional[models.NursingService]:
        """
        Retrieves a service by its primary key.

        Args:
            service_id (uuid.UUID): The ID of the service to retrieve.

        Returns:
            Optional[models.NursingService]: The NursingService object if found, otherwise None.
        """
        return self.db.get(models.NursingService, service_id)

    def get_by_name(self, *, service_name: str) -> Optional[models.NursingService]:
        """
        Retrieves a service by its unique name.

        Args:
            service_name (str): The name of the service.

        Returns:
            Optional[models.NursingService]: The NursingService object if found, otherwise None.
        """
        statement = select(models.NursingService).where(
            models.NursingService.service_name == service_name
        )
        return self.db.execute(statement).scalar_one_or_none()

    def update(
        self, *, service_id: uuid.UUID, updates: Dict[str, Any]
    ) -> Optional[models.NursingService]:
        """
        Updates an existing service's details.

        Args:
            service_id (uuid.UUID): The ID of the service to update.
            updates (Dict[str, Any]): A dictionary of fields to update.

        Returns:
            Optional[models.NursingService]: The updated NursingService object, or None if not found.
        """
        db_service = self.get_by_id(service_id=service_id)
        if not db_service:
            return None

        for key, value in updates.items():
            setattr(db_service, key, value)

        self.db.add(db_service)
        self.db.commit()
        self.db.refresh(db_service)
        return db_service

    def list_all(self, *, skip: int = 0, limit: int = 100) -> List[models.NursingService]:
        """
        Retrieves a paginated list of all services.

        Args:
            skip (int): The number of records to skip.
            limit (int): The maximum number of records to return.

        Returns:
            List[models.NursingService]: A list of NursingService objects.
        """
        statement = select(models.NursingService).offset(skip).limit(limit)
        return self.db.execute(statement).scalars().all()

    def delete(self, *, service_id: uuid.UUID) -> Optional[models.NursingService]:
        """
        Deletes a service from the database.
        Note: A soft delete (setting `is_active` to False) is often preferred
        and would typically be handled in the service layer.

        Args:
            service_id (uuid.UUID): The ID of the service to delete.

        Returns:
            Optional[models.NursingService]: The deleted NursingService object, or None if not found.
        """
        db_service = self.get_by_id(service_id=service_id)
        if not db_service:
            return None

        self.db.delete(db_service)
        self.db.commit()
        return db_service

    def search_available_nurses(
        self, 
        service_id: uuid.UUID, 
        patient_lat: float, 
        patient_lon: float, 
        requested_start_time: datetime, 
        requested_end_time: datetime,
        search_radius_meters: int = 8000
    ) -> List[models.Nurse]:
        """
        The ultimate matching engine. Filters by Service, Location, Vacations, 
        Existing Bookings, and specific Working Hours.
        """
        
        # 1. Fetch the requested service to understand the job type
        service = self.service_repo.get_by_id(service_id)
        if not service:
            raise ValueError("Service not found.")

        # 2. Define the Travel Buffer & PostGIS Target Point
        travel_buffer = timedelta(minutes=30)
        buffered_start = requested_start_time - travel_buffer
        buffered_end = requested_end_time + travel_buffer
        
        target_point = func.ST_SetSRID(func.ST_MakePoint(patient_lon, patient_lat), 4326)

        # --- EXCLUSION SUBQUERIES ---

        # Exclude 1: Nurses who have a vacation overlapping with the request
        overlapping_blackouts = self.db.query(models.BlackoutDate.nurse_id).filter(
            models.BlackoutDate.start_datetime < requested_end_time,
            models.BlackoutDate.end_datetime > requested_start_time
        ).subquery()

        # Exclude 2: Nurses who have an existing booking overlapping with the request + buffer
        overlapping_bookings = self.db.query(models.Booking.nurse_id).filter(
            models.Booking.booking_status == 'Confirmed',
            models.Booking.scheduled_start_time < buffered_end,
            models.Booking.scheduled_end_time > buffered_start
        ).subquery()

        # --- THE BASE QUERY (The "What" and "Where") ---
        
        query = self.db.query(models.Nurse).join(
            models.NurseAssociatedService, models.Nurse.id == models.NurseAssociatedService.nurse_id
        ).join(
            models.Address, models.Nurse.address_id == models.Address.id
        ).filter(
            models.NurseAssociatedService.service_id == service_id,
            func.ST_DWithin(models.Address.location, target_point, search_radius_meters),
            models.Nurse.is_verified == True,
            # Apply Universal Exclusions
            ~models.Nurse.id.in_(overlapping_blackouts),
            ~models.Nurse.id.in_(overlapping_bookings)
        )

        # --- THE DYNAMIC TIME FILTER ("The When") ---
        
        if service.schedule_type == 'Daily_Shift' or service.duration_type in ['hours', 'hour']:
            # For short jobs, we MUST ensure the requested time falls strictly inside their Working Hours
            
            # Extract the day of the week (0=Mon, 6=Sun) and the raw times
            req_day_of_week = requested_start_time.weekday()
            req_start_time_only = requested_start_time.time()
            req_end_time_only = requested_end_time.time()

            query = query.join(
                models.WorkingHours, models.Nurse.id == models.WorkingHours.nurse_id
            ).filter(
                models.WorkingHours.is_active == True,
                models.WorkingHours.day_of_week == req_day_of_week,
                models.WorkingHours.start_time <= req_start_time_only,
                models.WorkingHours.end_time >= req_end_time_only
            )
            
        elif service.schedule_type == 'Continuous':
            # For 24/7 jobs, we don't check WorkingHours. 
            # If they survived the blackout/booking exclusions above, they are good to go.
            pass

        # Execute and return the fully filtered list of available nurses
        return query.all()