"""Add database indexes for performance optimization

Revision ID: add_database_indexes
Revises: ce655b1b3ada
Create Date: 2026-03-22 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "add_database_indexes"
down_revision: Union[str, Sequence[str], None] = "ce655b1b3ada"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = "ccae44bc4921"


def upgrade() -> None:
    """Add indexes for frequently queried columns"""

    # ========== FOREIGN KEY INDEXES ==========
    # These are critical for JOIN performance

    # Patients
    op.create_index("ix_patients_address_id", "patients", ["address_id"])

    # Nurses
    op.create_index("ix_nurses_address_id", "nurses", ["address_id"])

    # Addresses
    op.create_index("ix_addresses_user_id", "addresses", ["user_id"])

    # Availability
    op.create_index("ix_availability_nurse_id", "availability", ["nurse_id"])

    # Bookings
    op.create_index("ix_bookings_patient_id", "bookings", ["patient_id"])
    op.create_index("ix_bookings_nurse_id", "bookings", ["nurse_id"])
    op.create_index("ix_bookings_service_id", "bookings", ["service_id"])
    op.create_index(
        "ix_bookings_booking_address_id", "bookings", ["booking_address_id"]
    )

    # Reviews
    op.create_index("ix_reviews_patient_id", "reviews", ["patient_id"])
    op.create_index("ix_reviews_nurse_id", "reviews", ["nurse_id"])

    # Payments
    op.create_index("ix_payments_patient_id", "payments", ["patient_id"])

    # Nurse Services (junction table)
    # Note: nurse_id is covered by composite PK (nurse_id, service_id)
    op.create_index(
        "ix_nurse_services_service_id", "nurse_services", ["service_id"]
    )  # For reverse lookups

    # Nurse Documents
    op.create_index("ix_nurse_documents_nurse_id", "nurse_documents", ["nurse_id"])

    # ========== FILTER COLUMN INDEXES ==========
    # These improve WHERE clause performance

    # Users
    op.create_index("ix_users_user_type", "users", ["user_type"])
    op.create_index("ix_users_is_active", "users", ["is_active"])
    # Note: users.email already has a unique index, no additional index needed

    # Nurses
    op.create_index("ix_nurses_is_verified", "nurses", ["is_verified"])
    op.create_index("ix_nurses_is_qualified", "nurses", ["is_qualified"])
    op.create_index("ix_nurses_is_active", "nurses", ["is_active"])

    # Nursing Services
    op.create_index("ix_nursing_services_is_active", "nursing_services", ["is_active"])
    op.create_index(
        "ix_nursing_services_is_qualified", "nursing_services", ["is_qualified"]
    )

    # Bookings
    op.create_index("ix_bookings_booking_status", "bookings", ["booking_status"])
    op.create_index("ix_bookings_payment_status", "bookings", ["payment_status"])

    # Availability
    op.create_index("ix_availability_is_booked", "availability", ["is_booked"])

    # Payments
    op.create_index("ix_payments_payment_status", "payments", ["payment_status"])

    # Nurse Documents
    op.create_index(
        "ix_nurse_documents_verification_status",
        "nurse_documents",
        ["verification_status"],
    )

    # ========== DATE/TIME INDEXES ==========
    # These improve range queries and sorting

    # Bookings
    op.create_index(
        "ix_bookings_scheduled_start_time", "bookings", ["scheduled_start_time"]
    )
    op.create_index(
        "ix_bookings_scheduled_end_time", "bookings", ["scheduled_end_time"]
    )
    op.create_index("ix_bookings_booking_time", "bookings", ["booking_time"])

    # Availability
    op.create_index("ix_availability_start_time", "availability", ["start_time"])
    op.create_index("ix_availability_end_time", "availability", ["end_time"])

    # Payments
    op.create_index("ix_payments_payment_date", "payments", ["payment_date"])

    # Reviews
    op.create_index("ix_reviews_review_date", "reviews", ["review_date"])

    # Users
    op.create_index("ix_users_created_at", "users", ["created_at"])
    op.create_index("ix_users_last_login_at", "users", ["last_login_at"])

    # ========== COMPOSITE INDEXES ==========
    # These optimize multi-column queries

    # Find available nurse slots
    op.create_index(
        "ix_availability_nurse_booked", "availability", ["nurse_id", "is_booked"]
    )

    # Find nurse's upcoming bookings by status
    op.create_index(
        "ix_bookings_nurse_status", "bookings", ["nurse_id", "booking_status"]
    )
    op.create_index(
        "ix_bookings_patient_status", "bookings", ["patient_id", "booking_status"]
    )

    # Find bookings in time range by status
    op.create_index(
        "ix_bookings_status_time",
        "bookings",
        ["booking_status", "scheduled_start_time"],
    )

    # Find verified and active nurses
    op.create_index("ix_nurses_verified_active", "nurses", ["is_verified", "is_active"])

    # Find available slot in time range for a nurse
    op.create_index(
        "ix_availability_nurse_time",
        "availability",
        ["nurse_id", "start_time", "end_time"],
    )

    # Location-based queries (if you implement geo-search)
    op.create_index("ix_addresses_city_state", "addresses", ["city", "state"])

    # Payment tracking
    op.create_index(
        "ix_payments_patient_status", "payments", ["patient_id", "payment_status"]
    )


def downgrade() -> None:
    """Remove all indexes"""

    # Composite indexes
    op.drop_index("ix_payments_patient_status", table_name="payments")
    op.drop_index("ix_addresses_city_state", table_name="addresses")
    op.drop_index("ix_availability_nurse_time", table_name="availability")
    op.drop_index("ix_nurses_verified_active", table_name="nurses")
    op.drop_index("ix_bookings_status_time", table_name="bookings")
    op.drop_index("ix_bookings_patient_status", table_name="bookings")
    op.drop_index("ix_bookings_nurse_status", table_name="bookings")
    op.drop_index("ix_availability_nurse_booked", table_name="availability")

    # Date/Time indexes
    op.drop_index("ix_users_last_login_at", table_name="users")
    op.drop_index("ix_users_created_at", table_name="users")
    op.drop_index("ix_reviews_review_date", table_name="reviews")
    op.drop_index("ix_payments_payment_date", table_name="payments")
    op.drop_index("ix_availability_end_time", table_name="availability")
    op.drop_index("ix_availability_start_time", table_name="availability")
    op.drop_index("ix_bookings_booking_time", table_name="bookings")
    op.drop_index("ix_bookings_scheduled_end_time", table_name="bookings")
    op.drop_index("ix_bookings_scheduled_start_time", table_name="bookings")

    # Filter column indexes
    op.drop_index(
        "ix_nurse_documents_verification_status", table_name="nurse_documents"
    )
    op.drop_index("ix_payments_payment_status", table_name="payments")
    op.drop_index("ix_availability_is_booked", table_name="availability")
    op.drop_index("ix_bookings_payment_status", table_name="bookings")
    op.drop_index("ix_bookings_booking_status", table_name="bookings")
    op.drop_index("ix_nursing_services_is_qualified", table_name="nursing_services")
    op.drop_index("ix_nursing_services_is_active", table_name="nursing_services")
    op.drop_index("ix_nurses_is_active", table_name="nurses")
    op.drop_index("ix_nurses_is_qualified", table_name="nurses")
    op.drop_index("ix_nurses_is_verified", table_name="nurses")
    # users.email index not dropped (never created - unique constraint handles it)
    op.drop_index("ix_users_is_active", table_name="users")
    op.drop_index("ix_users_user_type", table_name="users")

    # Foreign key indexes
    op.drop_index("ix_nurse_documents_nurse_id", table_name="nurse_documents")
    # nurse_services_nurse_id not dropped (never created - composite PK covers it)
    op.drop_index("ix_nurse_services_service_id", table_name="nurse_services")
    op.drop_index("ix_payments_patient_id", table_name="payments")
    op.drop_index("ix_reviews_nurse_id", table_name="reviews")
    op.drop_index("ix_reviews_patient_id", table_name="reviews")
    op.drop_index("ix_bookings_booking_address_id", table_name="bookings")
    op.drop_index("ix_bookings_service_id", table_name="bookings")
    op.drop_index("ix_bookings_nurse_id", table_name="bookings")
    op.drop_index("ix_bookings_patient_id", table_name="bookings")
    op.drop_index("ix_availability_nurse_id", table_name="availability")
    op.drop_index("ix_addresses_user_id", table_name="addresses")
    op.drop_index("ix_nurses_address_id", table_name="nurses")
    op.drop_index("ix_patients_address_id", table_name="patients")
