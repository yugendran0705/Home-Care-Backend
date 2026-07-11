import uuid
from sqlalchemy import (
    Column, String, Boolean, Float, Time, ForeignKey, Text, Integer, DateTime, Date, UUID, Numeric
)
from geoalchemy2 import Geography
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func # For default=func.now()

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column("user_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    user_type = Column(String(20), nullable=False, comment='ENUM: Patient, Nurse, Admin')
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True) # Nullable
    is_active = Column(Boolean, nullable=False, default=True)

    # Relationships
    patient = relationship("Patient", back_populates="user", uselist=False, primaryjoin="User.id == Patient.id")
    nurse = relationship("Nurse", back_populates="user", uselist=False, primaryjoin="User.id == Nurse.id")
    addresses = relationship("Address", back_populates="user")

class Patient(Base):
    __tablename__ = "patients"
    id = Column("patient_id", UUID(as_uuid=True), ForeignKey("users.user_id"), primary_key=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone_number = Column(String(20), unique=True, nullable=False)
    date_of_birth = Column(Date, nullable=True) # Nullable
    gender = Column(String(10), nullable=True, comment='ENUM: Male, Female, Other') # Nullable

    # Relationships
    user = relationship("User", back_populates="patient", uselist=False)
    bookings = relationship("Booking", back_populates="patient")
    reviews = relationship("Review", back_populates="patient")
    payments = relationship("Payment", back_populates="patient")

class Nurse(Base):
    __tablename__ = "nurses"
    id = Column("nurse_id", UUID(as_uuid=True), ForeignKey("users.user_id"), primary_key=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone_number = Column(String(20), unique=True, nullable=False)
    date_of_birth = Column(Date, nullable=True) # Nullable
    gender = Column(String(10), nullable=True, comment='ENUM: Male, Female, Other') # Nullable
    license_number = Column(String(50), unique=True, nullable=False)
    years_of_experience = Column(Integer, nullable=False, default=0)
    bio = Column(Text, nullable=True) # Nullable
    profile_picture_url = Column(String(255), nullable=False)
    is_verified = Column(Boolean, nullable=False, default=False)
    is_qualified = Column(Boolean, nullable=True, default=False)
    is_active = Column(Boolean, nullable=True, default=True)
    average_rating = Column(Numeric(3, 2), nullable=False, default=0.00) # DECIMAL(3,2) mapped to Numeric
    continuous_care_available = Column(Boolean, nullable=False, default=False)
    # Relationships
    user = relationship("User", back_populates="nurse", uselist=False)
    nurse_associated_services = relationship("NurseAssociatedService", back_populates="nurse")
    bookings = relationship("Booking", back_populates="nurse")
    reviews = relationship("Review", back_populates="nurse")
    documents = relationship("NurseDocument", back_populates="nurse")

class Address(Base):
    __tablename__ = "addresses"
    id = Column("address_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True) # Nullable, as per DBML
    address_line_1 = Column(String(255), nullable=False)
    address_line_2 = Column(String(255), nullable=True) # Nullable
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)
    pincode = Column(String(20), nullable=False)
    country = Column(String(100), nullable=False, default='India')
    latitude = Column(Numeric(10, 8), nullable=True) # Nullable
    longitude = Column(Numeric(11, 8), nullable=True) # Nullable
    location = Column(Geography(geometry_type='POINT', srid=4326, spatial_index=True))
    is_primary = Column(Boolean, nullable=False, default=False)

    # Relationships
    user = relationship("User", back_populates="addresses")
    # No direct relationship to Patient/Nurse here as they have foreign keys to Address.id
    # Bookings relationship is handled from Booking side

class NursingService(Base):
    __tablename__ = "nursing_services"
    id = Column("service_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True) # Nullable
    base_price = Column(Numeric(10, 2), nullable=False, default=0.00) # DECIMAL(10,2) mapped to Numeric
    duration = Column(Integer, nullable=True) # Nullable
    duration_type = Column(String(20), nullable=True, comment='ENUM: Minutes, Hours, Days') # Nullable
    schedule_type = Column(String(20), nullable=False, comment='ENUM: Continuous, Daily_Shift')
    shift_duration_hours = Column(Integer)
    is_active = Column(Boolean, nullable=False, default=True)
    is_qualified = Column(Boolean, nullable=False, default=False)

    # Relationships
    nurse_associated_services = relationship("NurseAssociatedService", back_populates="service")
    bookings = relationship("Booking", back_populates="service")

class NurseAssociatedService(Base):
    __tablename__ = "nurse_associated_services"
    # Composite primary key for the junction table
    nurse_id = Column(UUID(as_uuid=True), ForeignKey("nurses.nurse_id"), primary_key=True)
    service_id = Column(UUID(as_uuid=True), ForeignKey("nursing_services.service_id"), primary_key=True)

    # Relationships
    nurse = relationship("Nurse", back_populates="nurse_associated_services")
    service = relationship("NursingService", back_populates="nurse_associated_services")

class Booking(Base):
    __tablename__ = "bookings"
    id = Column("booking_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.booking_id"), nullable=True)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.patient_id"), nullable=False)
    nurse_id = Column(UUID(as_uuid=True), ForeignKey("nurses.nurse_id"), nullable=False)
    service_id = Column(UUID(as_uuid=True), ForeignKey("nursing_services.service_id"), nullable=False)
    is_parent_booking = Column(Boolean, nullable=False, default=False)
    booking_time = Column(DateTime(timezone=True), nullable=False, default=func.now())
    scheduled_start_time = Column(DateTime(timezone=True), nullable=False)
    scheduled_end_time = Column(DateTime(timezone=True), nullable=False)
    booking_status = Column(String(20), nullable=False, default='Pending', comment='ENUM: Pending, Confirmed, Completed, Cancelled, Rejected')
    total_amount = Column(Numeric(10, 2), nullable=False) # DECIMAL(10,2) mapped to Numeric
    payment_status = Column(String(20), nullable=False, default='Pending', comment='ENUM: Pending, Paid, Refunded, Failed')
    booking_address_id = Column(UUID(as_uuid=True), ForeignKey("addresses.address_id"), nullable=False)
    notes = Column(Text, nullable=True) # Nullable

    # Relationships
    patient = relationship("Patient", back_populates="bookings")
    nurse = relationship("Nurse", back_populates="bookings")
    service = relationship("NursingService", back_populates="bookings")
    booking_address = relationship("Address", primaryjoin="Booking.booking_address_id == Address.id")
    review = relationship("Review", back_populates="booking", uselist=False) # One review per booking
    payment = relationship("Payment", back_populates="booking", uselist=False) # One payment per booking
    child_bookings = relationship("Booking", backref=backref('parent', remote_side=[id]))

class Review(Base):
    __tablename__ = "reviews"
    id = Column("review_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.booking_id"), unique=True, nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.patient_id"), nullable=False)
    nurse_id = Column(UUID(as_uuid=True), ForeignKey("nurses.nurse_id"), nullable=False)
    rating = Column(Integer, nullable=False) # CHECK (rating >= 1 AND rating <= 5)
    comment = Column(Text, nullable=True) # Nullable
    review_date = Column(DateTime(timezone=True), nullable=False, default=func.now())

    # Relationships
    booking = relationship("Booking", back_populates="review")
    patient = relationship("Patient", back_populates="reviews")
    nurse = relationship("Nurse", back_populates="reviews")

class Payment(Base):
    __tablename__ = "payments"
    id = Column("payment_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.booking_id"), unique=True, nullable=False)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.patient_id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False) # DECIMAL(10,2) mapped to Numeric
    currency = Column(String(10), nullable=False, default='INR')
    payment_method = Column(String(50), nullable=True) # Nullable
    transaction_id = Column(String(255), unique=True, nullable=True) # Nullable
    payment_status = Column(String(20), nullable=False, default='Initiated', comment='ENUM: Initiated, Success, Failed, Refunded')
    payment_date = Column(DateTime(timezone=True), nullable=False, default=func.now())

    # Relationships
    booking = relationship("Booking", back_populates="payment")
    patient = relationship("Patient", back_populates="payments")

class NurseDocument(Base):
    __tablename__ = "nurse_documents"
    id = Column("document_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nurse_id = Column(UUID(as_uuid=True), ForeignKey("nurses.nurse_id"), nullable=False)
    document_type = Column(String(50), nullable=False, comment="ENUM: Aadhar, PAN, NursingLicense, Other")
    document_url = Column(String(255), nullable=False, comment="URL to the stored document (e.g., in an S3 bucket)")
    verification_status = Column(String(20), nullable=False, default='Pending', comment="ENUM: Pending, Approved, Rejected")
    notes = Column(Text, nullable=True, comment="Optional notes from an admin regarding verification")
    uploaded_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    verified_at = Column(DateTime(timezone=True), nullable=True)

    nurse = relationship("Nurse", back_populates="documents")

class WorkingHours(Base):
    """
    Stores the recurring weekly schedule for a nurse.
    """
    __tablename__ = "working_hours"
    id = Column("working_hours_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nurse_id = Column(UUID(as_uuid=True), ForeignKey("nurses.nurse_id", ondelete="CASCADE"), nullable=False)
    
    # 0 = Monday, 1 = Tuesday, ..., 6 = Sunday
    day_of_week = Column(Integer, nullable=False) 
    
    start_time = Column(Time(timezone=True), nullable=False)
    end_time = Column(Time(timezone=True), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    # Relationship back to the nurse
    nurse = relationship("Nurse", backref="working_hours")


class BlackoutDate(Base):
    """
    Stores specific vacation or time-off dates where a nurse is unavailable.
    """
    __tablename__ = "blackout_dates"
    id = Column("blackout_date_id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nurse_id = Column(UUID(as_uuid=True), ForeignKey("nurses.nurse_id", ondelete="CASCADE"), nullable=False)
    
    start_datetime = Column(DateTime(timezone=True), nullable=False)
    end_datetime = Column(DateTime(timezone=True), nullable=False)
    reason = Column(String(255), nullable=True) # E.g., "Sick leave", "Vacation"

    # Relationship back to the nurse
    nurse = relationship("Nurse", backref="blackout_dates")