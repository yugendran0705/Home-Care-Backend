# services/bookings.py

from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from typing import List
import uuid

import models
from repositories.nursing_services import NursingServiceRepository

class BookingService:
    def __init__(self, db: Session):
        self.db = db
        self.service_repo = NursingServiceRepository(db)

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
        travel_buffer = timedelta(hours=1)
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
            models.NurseService, models.Nurse.id == models.NurseService.nurse_id
        ).join(
            models.Address, models.Nurse.address_id == models.Address.id
        ).filter(
            models.NurseService.service_id == service_id,
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