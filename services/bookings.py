from sqlalchemy.orm import Session
from repositories.bookings import BookingRepository
from schemas.bookings import *
import models
from fastapi import HTTPException,status
class BookingService:


    def __init__(self,db:Session):

        self.db=db
        self.booking_repo = BookingRepository(db)
    def create_booking(self,*,booking_in:BookingCreate)-> models.Booking:
        
       
        nurse_bookings = self.booking_repo.get_for_nurse(nurse_id=booking_in.nurse_id)
        for booking in nurse_bookings:
            if(booking.scheduled_start_time<=booking_in.scheduled_start_time <= booking.scheduled_end_time or booking.scheduled_start_time<=booking_in.scheduled_end_time <= booking.scheduled_end_time or booking_in.scheduled_start_time<=booking.scheduled_start_time<=booking.scheduled_end_time ):
                raise Exception("Nurse already booked in the selected time!")

        
        booking_service = self.booking_repo.create(booking_in = booking_in)

        return booking_service
        