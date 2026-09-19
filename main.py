import logging

from fastapi import FastAPI
from dotenv import load_dotenv
import models as model
from config.database import engine
from utils.logger import logger

from views import nurse_associated_services, patients, users, address, nurses, nursing_services, payments, working_hours, blackout_dates, bookings, reviews, notifications
from fastapi.middleware.cors import CORSMiddleware

# Configure the application-wide logger once, at startup. Every module logs
# through utils.logger.logger, which propagates to this root configuration.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(
    title="Home Care Backend API",
    description="API for patients to book nurses available in their area.",
    version="0.1.0",
)

load_dotenv()

origins = [
    "http://localhost:8081",  # React app
    "http://localhost:8000",  # FastAPI app (if you're testing directly)
    "http://192.168.29.240:8000",  # Local network IP
    "*",  # Allow all origins (not recommended for production)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

model.Base.metadata.create_all(bind=engine)
logger.info("Home Care Backend starting up.")

app.include_router(users.router, prefix="/api/v1")
app.include_router(patients.router, prefix="/api/v1")
app.include_router(address.router, prefix="/api/v1")
app.include_router(nurses.router, prefix="/api/v1")
app.include_router(nursing_services.router, prefix="/api/v1")
app.include_router(nurse_associated_services.router, prefix="/api/v1")
app.include_router(working_hours.router, prefix="/api/v1")
app.include_router(blackout_dates.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(bookings.router, prefix="/api/v1")
app.include_router(reviews.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")

@app.get("/")
async def read_root():
    """
    Root endpoint for the Nurse Booking Backend.
    """
    return {"message": "Welcome to the Home Care Backend! FastAPI is running!"}


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "ok"}
