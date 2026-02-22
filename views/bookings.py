from fastapi import APIRouter,Depends,HTTPException,status
from schemas.bookings import *
from config.database import get_db
from services.bookings import BookingService
from utils.roleChecker import RoleChecker
import models
router = APIRouter(prefix="/bookings",tags=["bookings"])

def get_bookings_service(db = Depends(get_db)):
    return BookingService(db)

patient_dependency = Depends(RoleChecker(allowed_roles=["Admin","Patient"]))

@router.post("/",response_model = BookingResponse,summary="Create new booking")
def create_new_booking(booking_in:BookingCreate,
                       service:BookingService = Depends(get_bookings_service),
                       current_user:models.User = patient_dependency):
    try:
        new_booking=service.create_booking(booking_in=booking_in)
    except Exception as e:
        print(f"Error:{e}")
        raise HTTPException(status_code=500,detail=f"Error in creating booking: {e}")
    

    
    return new_booking
    
        