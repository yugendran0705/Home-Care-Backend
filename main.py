from fastapi import FastAPI
from dotenv import load_dotenv
import models as model
from config.database import engine

from views import nurse_associated_services, patients, users, address, nurses, nursing_services, working_hours
from fastapi.middleware.cors import CORSMiddleware

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
    "*"  # Allow all origins (not recommended for production)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

model.Base.metadata.create_all(bind=engine)

app.include_router(users.router, prefix="/api/v1")
app.include_router(patients.router, prefix="/api/v1")
app.include_router(address.router, prefix="/api/v1")
app.include_router(nurses.router, prefix="/api/v1")
app.include_router(nursing_services.router, prefix="/api/v1")
app.include_router(nurse_associated_services.router, prefix="/api/v1")
app.include_router(working_hours.router, prefix="/api/v1")

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
