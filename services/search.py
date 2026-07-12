from datetime import timedelta
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from repositories.nurses import NurseRepository
from repositories.nursing_services import NursingServiceRepository
from schemas.search import NurseSearchRequest, NurseSearchResponse


class SearchService:
    """Service layer for searching available nurses."""

    def __init__(self, db: Session):
        self.db = db
        self.nurse_repo = NurseRepository(db)
        self.service_repo = NursingServiceRepository(db)

    def search_available_nurses(self, search_request: NurseSearchRequest) -> List[NurseSearchResponse]:
        """Return nurses that match the requested service, location, and time window."""
        service = self.service_repo.get_by_id(service_id=search_request.service_id)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service not found.",
            )

        requested_start_time = search_request.requested_start_time
        requested_end_time = requested_start_time

        if service.duration_type and service.duration is not None:
            duration_type = str(service.duration_type).lower()
            if duration_type == "minutes":
                requested_end_time = requested_start_time + timedelta(
                    minutes=service.duration
                )
            elif duration_type == "hours":
                requested_end_time = requested_start_time + timedelta(
                    hours=service.duration
                )
            elif duration_type == "days":
                requested_end_time = requested_start_time + timedelta(
                    days=service.duration
                )
        elif service.schedule_type == "Daily_Shift" and service.shift_duration_hours:
            requested_end_time = requested_start_time + timedelta(
                hours=service.shift_duration_hours
            )

        nurses = self.nurse_repo.search_available_nurses(
            service_id=search_request.service_id,
            patient_lat=search_request.patient_latitude,
            patient_lon=search_request.patient_longitude,
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
