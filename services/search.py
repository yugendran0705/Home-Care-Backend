import uuid
from datetime import timedelta
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from repositories.nurses import NurseRepository
from repositories.nursing_services import NursingServiceRepository
from repositories.address import AddressRepository
from schemas.search import NurseSearchRequest, NurseSearchResponse
from utils.time_calculator import calculate_end_time, get_total_days


class SearchService:
    """Service layer for searching available nurses."""

    def __init__(self, db: Session):
        self.db = db
        self.nurse_repo = NurseRepository(db)
        self.service_repo = NursingServiceRepository(db)
        self.address_repo = AddressRepository(db)

    def search_available_nurses(
        self, search_request: NurseSearchRequest, patient_id: uuid.UUID
    ) -> List[NurseSearchResponse]:
        """
        Return nurses that match the requested service, location, and time
        window. Location is the authenticated patient's primary address, not
        caller-supplied coordinates.
        """
        primary_address = self.address_repo.get_primary_for_user(patient_id)
        if not primary_address or primary_address.latitude is None or primary_address.longitude is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You must have a primary address with a set location to search for nurses.",
            )

        service = self.service_repo.get_by_id(service_id=search_request.service_id)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service not found.",
            )

        requested_start_time = search_request.requested_start_time
        duration_type = (service.duration_type or "").lower()
        if service.duration is None or not duration_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Service is missing duration/duration_type configuration.",
            )
        if service.schedule_type == "Daily_Shift":
            if duration_type not in {"day", "days", "week", "weeks"}:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Daily_Shift duration_type must be days/weeks, got: {service.duration_type}",
                )
            if not service.shift_duration_hours:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Daily_Shift services must have shift_duration_hours defined.",
                )
            total_days = get_total_days(service.duration, duration_type)
            last_shift_start = requested_start_time + timedelta(days=total_days - 1)
            requested_end_time = last_shift_start + timedelta(
                hours=service.shift_duration_hours
            )
        elif service.schedule_type == "Continuous":
            requested_end_time = calculate_end_time(
                requested_start_time, service.duration, service.duration_type
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown schedule_type: {service.schedule_type}",
            )

        nurses = self.nurse_repo.search_available_nurses(
            service_id=search_request.service_id,
            patient_lat=float(primary_address.latitude),
            patient_lon=float(primary_address.longitude),
            requested_start_time=requested_start_time,
            requested_end_time=requested_end_time,
            search_radius_meters=search_request.radius_meters or 8000,
        )

        results: List[NurseSearchResponse] = []
        for nurse in nurses:
            results.append(
                NurseSearchResponse(
                    nurse_id=nurse.id,
                    first_name=nurse.first_name,
                    last_name=nurse.last_name,
                    phone_number=nurse.phone_number,
                    years_of_experience=nurse.years_of_experience,
                    bio=nurse.bio,
                    profile_picture_url=nurse.profile_picture_url,
                    average_rating=float(getattr(nurse, "average_rating", 0) or 0),
                    distance_meters=None,
                )
            )

        return results
