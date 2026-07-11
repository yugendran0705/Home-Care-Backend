# services/bookings.py
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid

import models
from repositories.bookings import BookingRepository
from repositories.nursing_services import NursingServiceRepository
from utils.time_calculator import calculate_end_time, get_total_days

class BookingService:
    def __init__(self, db: Session):
        self.db = db
        self.booking_repo = BookingRepository(db)
        self.service_repo = NursingServiceRepository(db)

    def create_pending_booking(
        self, 
        patient_id: uuid.UUID, 
        nurse_id: uuid.UUID, 
        service_id: uuid.UUID, 
        scheduled_start_time: datetime,
        booking_address_id: uuid.UUID,
        notes: str = None
    ) -> models.Booking:
        """
        Creates a pending booking, branching into Parent-Child shifts if necessary.
        """
        service = self.service_repo.get_by_id(service_id)
        if not service:
            raise ValueError("Service not found.")

        # Shared base data for all booking records
        base_booking_data = {
            "patient_id": patient_id,
            "nurse_id": nurse_id,
            "service_id": service_id,
            "booking_status": "Pending",
            "total_amount": service.base_price,
            "payment_status": "Pending",
            "booking_address_id": booking_address_id,
            "notes": notes,
            "parent_booking_id": None # Default to None
        }

        # -------------------------------------------------------------------
        # BRANCH 1: Continuous Care (e.g., Live-in for 2 weeks)
        # -------------------------------------------------------------------
        if service.schedule_type == 'Continuous':
            end_time = calculate_end_time(scheduled_start_time, service.duration, service.duration_type)
            
            booking_data = {
                **base_booking_data,
                "scheduled_start_time": scheduled_start_time,
                "scheduled_end_time": end_time
            }
            return self.booking_repo.create(booking_in=booking_data)

        # -------------------------------------------------------------------
        # BRANCH 2: Daily Shifts (e.g., 8 hrs/day for 14 days)
        # -------------------------------------------------------------------
        elif service.schedule_type == 'Daily_Shift':
            if not service.shift_duration_hours:
                raise ValueError("Daily_Shift services must have a shift_duration_hours defined.")

            # 1. Create the PARENT Booking (Acts as a wrapper for billing/UI)
            parent_end_time = calculate_end_time(scheduled_start_time, service.duration, service.duration_type)
            
            parent_data = {
                **base_booking_data,
                "scheduled_start_time": scheduled_start_time,
                "scheduled_end_time": parent_end_time,
                "is_parent_booking": True
            }
            parent_booking = self.booking_repo.create(booking_in=parent_data)

            # 2. Create the CHILD Bookings (The actual working shifts)
            total_days = get_total_days(service.duration, service.duration_type)
            child_bookings_data = []

            for day_offset in range(total_days):
                shift_start = scheduled_start_time + timedelta(days=day_offset)
                shift_end = shift_start + timedelta(hours=service.shift_duration_hours)

                child_data = {
                    **base_booking_data,
                    "parent_booking_id": parent_booking.id, # Link to parent
                    "scheduled_start_time": shift_start,
                    "scheduled_end_time": shift_end,
                }
                child_bookings_data.append(child_data)

            # Insert all child shifts at once
            self.booking_repo.bulk_create(child_bookings_data)

            return parent_booking

        else:
            raise ValueError(f"Unknown schedule type: {service.schedule_type}")