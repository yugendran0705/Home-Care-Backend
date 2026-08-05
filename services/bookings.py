# services/bookings.py
import time as time_module
import uuid
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models
from repositories.bookings import BookingRepository
from repositories.nurses import NurseRepository
from repositories.nursing_services import NursingServiceRepository
from repositories.payments import PaymentRepository
from repositories.blackout_dates import BlackoutDateRepository
from repositories.working_hours import WorkingHoursRepository
from repositories.address import AddressRepository
from utils.scheduling import compute_service_windows, compute_required_segments
from utils.redis import (
    nurse_booking_lock,
    schedule_booking_expiry,
    cancel_booking_expiry,
    BOOKING_EXPIRY_SECONDS,
    LockAcquisitionError,
)


class BookingService:
    # NOTE: a Pending booking blocks its slot until the expiry sweeper flips it
    # to Cancelled - there is deliberately no age cutoff in the availability
    # check. See BookingRepository.find_conflicting for why.

    # Buffer for travel between back-to-back assignments (matches search logic).
    TRAVEL_BUFFER = timedelta(minutes=30)

    # Hard service-area cap enforced at booking time, independent of whatever
    # radius_meters a client passed to /search - a nurse_id obtained any other
    # way must still fall within this distance of the patient's primary address.
    MAX_BOOKING_DISTANCE_METERS = 8000

    def __init__(self, db: Session):
        self.db = db
        self.booking_repo = BookingRepository(db)
        self.nurse_repo = NurseRepository(db)
        self.service_repo = NursingServiceRepository(db)
        self.payment_repo = PaymentRepository(db)
        self.blackout_repo = BlackoutDateRepository(db)
        self.working_hours_repo = WorkingHoursRepository(db)
        self.address_repo = AddressRepository(db)

    # ------------------------------------------------------------------
    # Availability decision (business logic - orchestrates repo queries)
    # ------------------------------------------------------------------
    def _assert_nurse_available(
        self, nurse_id: uuid.UUID, patient_id: uuid.UUID, service, windows
    ) -> None:
        nurse = self.db.get(models.Nurse, nurse_id)
        if not nurse or not nurse.is_verified or not nurse.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Nurse is not available for booking.",
            )

        patient_address = self.address_repo.get_primary_for_user(patient_id)
        if (
            not patient_address
            or patient_address.latitude is None
            or patient_address.longitude is None
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You must have a primary address with a set location to book a nurse.",
            )
        if not self.nurse_repo.is_within_distance(
            nurse_id=nurse_id,
            patient_lat=float(patient_address.latitude),
            patient_lon=float(patient_address.longitude),
            radius_meters=self.MAX_BOOKING_DISTANCE_METERS,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Nurse is outside your service area.",
            )

        if service.schedule_type == "Continuous" and not nurse.continuous_care_available:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Nurse is not available for continuous care.",
            )

        if self.blackout_repo.has_overlap(nurse_id=nurse_id, windows=windows):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Nurse is on leave during the requested time.",
            )

        if self.booking_repo.find_conflicting(
            nurse_id=nurse_id,
            windows=windows,
            travel_buffer=self.TRAVEL_BUFFER,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Nurse is already booked for the selected time.",
            )

        if service.schedule_type == "Daily_Shift":
            required_segments = compute_required_segments(windows)
            if not self.working_hours_repo.is_shift_covered(
                nurse_id=nurse_id, segments=required_segments
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Nurse does not work during the requested shift hours.",
                )

    # ------------------------------------------------------------------
    # Create pending booking + pending payment (atomic, lock-guarded)
    # ------------------------------------------------------------------
    def create_booking(
        self,
        patient_id: uuid.UUID,
        nurse_id: uuid.UUID,
        service_id: uuid.UUID,
        scheduled_start_time: datetime,
        booking_address_id: uuid.UUID,
        notes: str = None,
    ) -> dict:
        """
        Creates a Pending booking + its Pending Payment, then schedules a
        cancellation timer on the Redis delayed queue (ZSET).

        Concurrency safety:
          1. Per-nurse Redis lock serializes availability-check + insert, so two
             simultaneous requests can't both see the nurse as free.
          2. Booking(s) + Payment are inserted in ONE transaction and committed
             together - never a booking without a payment.
          3. The committed Pending row holds the slot afterwards (the lock is
             released on commit); the ZSET timer cancels it if left unpaid.

        For Continuous services this creates a single standalone Booking. For
        Daily_Shift services it creates a parent Booking (billing wrapper,
        holds the Payment) plus one child Booking per shift day.
        """
        service = self.service_repo.get_by_id(service_id=service_id)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Service not found."
            )
        if service.duration is None or not service.duration_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Service is missing duration/duration_type configuration.",
            )

        try:
            windows = compute_service_windows(service, scheduled_start_time)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

        try:
            with nurse_booking_lock(nurse_id):
                try:
                    self._assert_nurse_available(nurse_id, patient_id, service, windows)

                    base = {
                        "patient_id": patient_id,
                        "nurse_id": nurse_id,
                        "service_id": service_id,
                        "total_amount": service.base_price,
                        "booking_address_id": booking_address_id,
                        "notes": notes,
                    }

                    if service.schedule_type == "Continuous":
                        booking = self.booking_repo.add(
                            models.Booking(
                                **base,
                                scheduled_start_time=windows[0][0],
                                scheduled_end_time=windows[0][1],
                            )
                        )
                    else:  # Daily_Shift: parent wrapper + one child per shift
                        booking = self.booking_repo.add(
                            models.Booking(
                                **base,
                                scheduled_start_time=windows[0][0],
                                scheduled_end_time=windows[-1][1],
                                is_parent_booking=True,
                            )
                        )
                        self.booking_repo.add_all(
                            [
                                models.Booking(
                                    **base,
                                    parent_booking_id=booking.id,
                                    scheduled_start_time=shift_start,
                                    scheduled_end_time=shift_end,
                                )
                                for shift_start, shift_end in windows
                            ]
                        )

                    # Payment always attaches to `booking` here - the standalone
                    # Continuous booking, or the Daily_Shift parent. Never a
                    # child shift; those share the parent's payment/status.
                    payment = self.payment_repo.add(
                        models.Payment(
                            booking_id=booking.id,
                            patient_id=patient_id,
                            amount=service.base_price,
                            payment_status="Initiated",
                        )
                    )

                    self.db.commit()
                except Exception:
                    self.db.rollback()
                    raise
        except LockAcquisitionError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

        self.db.refresh(booking)
        self.db.refresh(payment)

        # Scheduled AFTER commit - absolute epoch timestamp, timezone-agnostic.
        schedule_booking_expiry(booking.id, time_module.time() + BOOKING_EXPIRY_SECONDS)
        return {"booking": booking, "payment": payment}

    # ------------------------------------------------------------------
    # Payment succeeded -> confirm booking (atomic, row-locked)
    # ------------------------------------------------------------------
    def confirm_booking(
        self,
        booking_id: uuid.UUID,
        transaction_id: str = None,
        payment_method: str = None,
    ) -> models.Booking:
        """
        `booking_id` must be the booking that holds the Payment: a standalone
        Continuous booking, or a Daily_Shift parent. Child shifts share the
        parent's Payment and are cascaded automatically - they don't have
        their own and can't be confirmed individually.
        """
        try:
            booking = self._get_payment_holder_for_update(booking_id)

            if booking.booking_status == "Confirmed":
                self.db.rollback()
                return booking  # idempotent (webhook redelivery)

            if booking.booking_status != "Pending":
                # Cancelled before payment landed (last-second race). The charge
                # needs to be voided/refunded by the caller - this is not silent.
                self.db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Booking is '{booking.booking_status}', cannot confirm payment. "
                        "Reconcile the payment (void/refund)."
                    ),
                )

            payment = self.payment_repo.get_by_booking_id(booking_id=booking.id)
            if not payment:
                self.db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Payment record not found for this booking.",
                )

            self.payment_repo.set_status(
                payment=payment,
                payment_status="Success",
                transaction_id=transaction_id,
                payment_method=payment_method,
            )
            self.booking_repo.set_status(
                booking=booking, booking_status="Confirmed", payment_status="Paid"
            )
            # No-op for a standalone Continuous booking (zero rows have this
            # parent_booking_id); cascades to every shift for a Daily_Shift parent.
            self.booking_repo.cascade_children_status(
                parent_booking_id=booking.id,
                booking_status="Confirmed",
                payment_status="Paid",
            )

            self.db.commit()
        except HTTPException:
            raise
        except Exception:
            self.db.rollback()
            raise

        cancel_booking_expiry(booking.id)  # slot confirmed; drop the timer
        self.db.refresh(booking)
        return booking

    # ------------------------------------------------------------------
    # Payment failed / 10-min timeout -> cancel booking (atomic, row-locked)
    # ------------------------------------------------------------------
    def fail_booking(self, booking_id: uuid.UUID, transaction_id: str = None) -> models.Booking:
        """
        Payment gateway reported failure -> cancel the (still-Pending) booking.
        Raises 409 if the booking was already Confirmed: that means payment
        actually succeeded before this failure callback arrived, a genuine
        conflict between signals that must be surfaced (and reconciled -
        void/refund) rather than silently returning 200 with the booking
        untouched.
        """
        return self._cancel_if_pending(
            booking_id, transaction_id=transaction_id, raise_if_already_confirmed=True
        )

    def cancel_if_still_pending(self, booking_id: uuid.UUID):
        """
        Called by the expiry sweeper when the ZSET timer fires. Finding the
        booking already Confirmed here is the EXPECTED outcome of the
        webhook-vs-timer race (the webhook won) - a silent no-op, not an error.
        Already-Cancelled is likewise a harmless idempotent no-op.
        """
        return self._cancel_if_pending(booking_id, silent_if_missing=True)

    def _cancel_if_pending(
        self,
        booking_id: uuid.UUID,
        transaction_id: str = None,
        silent_if_missing: bool = False,
        raise_if_already_confirmed: bool = False,
    ):
        try:
            try:
                booking = self._get_payment_holder_for_update(booking_id)
            except HTTPException:
                if silent_if_missing:
                    self.db.rollback()
                    return None
                raise

            if booking.booking_status == "Confirmed":
                self.db.rollback()
                if raise_if_already_confirmed:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Booking is already Confirmed/Paid; a payment-failed "
                            "callback arrived after success was already processed. "
                            "Reconcile with the payment gateway (void/refund) manually."
                        ),
                    )
                return booking  # sweeper: expected race outcome, not an error

            # Idempotent: already Cancelled -> leave it alone, no error either way.
            if booking.booking_status != "Pending":
                self.db.rollback()
                return booking

            self.booking_repo.set_status(
                booking=booking, booking_status="Cancelled", payment_status="Failed"
            )

            payment = self.payment_repo.get_by_booking_id(booking_id=booking.id)
            if payment and payment.payment_status not in ("Success", "Refunded"):
                self.payment_repo.set_status(
                    payment=payment,
                    payment_status="Failed",
                    transaction_id=transaction_id,
                )

            self.booking_repo.cascade_children_status(
                parent_booking_id=booking.id,
                booking_status="Cancelled",
                payment_status="Failed",
            )

            self.db.commit()
        except HTTPException:
            raise
        except Exception:
            self.db.rollback()
            raise

        cancel_booking_expiry(booking.id)  # remove timer if still present
        self.db.refresh(booking)
        return booking

    # ------------------------------------------------------------------
    # Read-only lookups
    # ------------------------------------------------------------------
    def get_bookings_for_patient(self, *, patient_id: uuid.UUID) -> List[models.Booking]:
        return self.booking_repo.get_for_patient(patient_id=patient_id)

    def get_bookings_for_nurse(self, *, nurse_id: uuid.UUID) -> List[models.Booking]:
        return self.booking_repo.get_for_nurse(nurse_id=nurse_id)

    # ------------------------------------------------------------------
    def _get_payment_holder_for_update(self, booking_id: uuid.UUID) -> models.Booking:
        """
        Row-locks and returns the booking identified by `booking_id`, rejecting
        it if it's a Daily_Shift child (those have no Payment of their own -
        the caller must target the parent instead).
        """
        booking = self.booking_repo.get_for_update(booking_id=booking_id)
        if not booking:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found."
            )
        if booking.parent_booking_id is not None:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "This is an individual shift of a Daily_Shift booking and has "
                    "no payment of its own; operate on its parent_booking_id instead."
                ),
            )
        return booking
