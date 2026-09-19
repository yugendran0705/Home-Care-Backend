# services/bookings.py
import secrets
import time as time_module
import uuid
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from utils.logger import logger

import models
from repositories.bookings import BookingRepository
from repositories.nurses import NurseRepository
from repositories.nursing_services import NursingServiceRepository
from repositories.payments import PaymentRepository
from repositories.blackout_dates import BlackoutDateRepository
from repositories.working_hours import WorkingHoursRepository
from repositories.address import AddressRepository
from config.razorpay import get_razorpay_client
from utils.scheduling import compute_service_windows, compute_required_segments
from utils.redis import (
    nurse_booking_lock,
    schedule_booking_expiry_with_retry,
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

    # Wrong-code budget before a booking's handover code has to be reissued,
    # so a 6-digit code can't be walked through by a nurse who never showed up.
    MAX_OTP_ATTEMPTS = 5

    def __init__(self, db: Session, razorpay_client=None):
        self.db = db
        self.booking_repo = BookingRepository(db)
        self.nurse_repo = NurseRepository(db)
        self.service_repo = NursingServiceRepository(db)
        self.payment_repo = PaymentRepository(db)
        self.blackout_repo = BlackoutDateRepository(db)
        self.working_hours_repo = WorkingHoursRepository(db)
        self.address_repo = AddressRepository(db)
        # Lazy: built on first access (see `razorpay` property) rather than
        # here, so call sites that never touch payments (e.g. the expiry
        # sweeper, which only calls cancel_if_still_pending) don't crash on
        # missing/invalid Razorpay credentials in their deployment env.
        self._razorpay_client = razorpay_client

    @property
    def razorpay(self):
        if self._razorpay_client is None:
            self._razorpay_client = get_razorpay_client()
        return self._razorpay_client

    # ------------------------------------------------------------------
    # Availability decision (business logic - orchestrates repo queries)
    # ------------------------------------------------------------------
    def _assert_nurse_available(
        self, nurse_id: uuid.UUID, patient_id: uuid.UUID, service, windows
    ) -> models.Address:
        """
        Returns the patient's primary address (also the resolved booking
        address - see create_booking) after validating the nurse is bookable.
        """
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

        return patient_address

    # ------------------------------------------------------------------
    # Create pending booking + pending payment (atomic, lock-guarded)
    # ------------------------------------------------------------------
    def create_booking(
        self,
        patient_id: uuid.UUID,
        nurse_id: uuid.UUID,
        service_id: uuid.UUID,
        scheduled_start_time: datetime,
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

        booking_address_id is always the patient's primary address, resolved
        server-side - never a client-supplied field (avoids IDOR).
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
                    patient_address = self._assert_nurse_available(
                        nurse_id, patient_id, service, windows
                    )

                    base = {
                        "patient_id": patient_id,
                        "nurse_id": nurse_id,
                        "service_id": service_id,
                        "total_amount": service.base_price,
                        "booking_address_id": patient_address.id,
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

        # Razorpay order creation (external call) happens AFTER commit, same
        # reasoning as the expiry-timer scheduling below: keep the nurse lock
        # held for as little time as possible. If the gateway call fails,
        # there's no way for the patient to ever pay for this booking, so
        # cancel it outright rather than leaving it Pending.
        try:
            rp_order = self.razorpay.order.create(
                data={
                    # Razorpay expects amount as an integer in the currency's
                    # smallest unit (paise for INR), not rupees.
                    "amount": int(payment.amount * 100),
                    "currency": payment.currency,
                    "receipt": str(payment.id),
                }
            )
        except Exception:
            logger.exception(
                "Razorpay order creation failed for booking %s / payment %s; cancelling.",
                booking.id, payment.id,
            )
            self.payment_repo.update(
                payment_id=payment.id,
                updates={"failure_reason": "Gateway order creation failed"},
            )
            try:
                self._cancel_if_pending(booking.id)
            except Exception:
                logger.exception(
                    "Compensating cancel also failed for booking %s after a gateway "
                    "order-creation failure.",
                    booking.id,
                )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not initiate payment with the payment gateway. Please try again.",
            )

        try:
            payment = self.payment_repo.update(
                payment_id=payment.id,
                updates={"gateway_order_id": rp_order["id"]},
            )
        except Exception:
            logger.exception(
                "Persisting gateway_order_id failed for booking %s / payment %s; cancelling.",
                booking.id, payment.id,
            )
            try:
                self._cancel_if_pending(booking.id)
            except Exception:
                logger.exception(
                    "Compensating cancel also failed for booking %s after a "
                    "gateway_order_id persistence failure.",
                    booking.id,
                )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Booking could not be completed due to a temporary system issue. Please try again.",
            )

        # Scheduled AFTER commit - absolute epoch timestamp, timezone-agnostic.
        # A Pending booking with no timer would block this nurse's slot forever
        # (find_conflicting has no age cutoff by design). If Redis is still
        # unreachable after schedule_booking_expiry_with_retry's own retries,
        # fail closed: cancel the booking through the same path a payment
        # failure/timeout would use, rather than returning success for an
        # unprotected booking.
        if not schedule_booking_expiry_with_retry(
            booking.id, time_module.time() + BOOKING_EXPIRY_SECONDS
        ):
            logger.error(
                "Could not schedule expiry timer for booking %s; cancelling.", booking.id
            )
            try:
                self._cancel_if_pending(booking.id)
            except Exception:
                logger.exception(
                    "Compensating cancel also failed for booking %s; it may be stuck "
                    "Pending with no expiry timer until the reconciliation backstop "
                    "catches it.",
                    booking.id,
                )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Booking could not be completed due to a temporary system issue. Please try again.",
            )

        return {
            "booking": booking,
            "payment": payment,
            "razorpay_key_id": self.razorpay.auth[0],
        }

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
            # Clear any failure_reason left over from an earlier declined
            # attempt on this same order - fail_booking no longer cancels on
            # a decline (see fail_booking), so a Success here commonly
            # follows one or more failed attempts, and a stale decline
            # message on an otherwise-successful payment is confusing.
            payment.failure_reason = None
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
    # Payment attempt declined -> record it, but keep the booking Pending
    # ------------------------------------------------------------------
    def fail_booking(self, booking_id: uuid.UUID, transaction_id: str = None) -> models.Booking:
        """
        Payment gateway reported a declined/failed attempt against this
        booking's order. This intentionally does NOT cancel the booking.

        Razorpay (like most gateways) lets a customer retry a different
        card against the SAME order after a decline, and fires
        payment.failed per attempt - not once, when the order is actually
        abandoned. Cancelling here would release the nurse's slot on the
        first declined card; if a retry then succeeded, confirm_booking
        would refuse to confirm a booking that's no longer Pending, and
        the successful charge would be stranded with nothing in our system
        reflecting it. Only the expiry-timeout sweeper
        (cancel_if_still_pending) or an explicit customer cancellation
        actually cancels a Pending booking now.
        """
        try:
            booking = self._get_payment_holder_for_update(booking_id)

            if booking.booking_status != "Pending":
                # Already Confirmed (this failure is for a stale/earlier
                # attempt that lost the race) or already Cancelled (expired
                # via the sweeper) - terminal state wins, leave it alone.
                self.db.rollback()
                return booking

            payment = self.payment_repo.get_by_booking_id(booking_id=booking.id)
            if payment and payment.payment_status not in ("Success", "Refunded"):
                self.payment_repo.set_status(
                    payment=payment,
                    payment_status="Failed",
                    transaction_id=transaction_id,
                )

            self.db.commit()
        except HTTPException:
            raise
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(booking)
        return booking

    def cancel_if_still_pending(self, booking_id: uuid.UUID):
        """
        Called by the expiry sweeper when the ZSET timer fires - the only
        remaining path that actually cancels a Pending booking (see
        fail_booking for why a payment decline no longer does). Finding the
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
    ):
        try:
            try:
                booking = self._get_payment_holder_for_update(booking_id)
            except HTTPException:
                if silent_if_missing:
                    self.db.rollback()
                    return None
                raise

            # Idempotent: already terminal (Confirmed or Cancelled) -> leave
            # it alone, no error either way.
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
    # Visit handover: the patient reads a code, the nurse redeems it
    # ------------------------------------------------------------------
    def get_completion_otp(
        self, *, booking_id: uuid.UUID, patient_id: uuid.UUID
    ) -> models.Booking:
        """
        Returns the booking's handover code, issuing one only on the first read
        (when none exists yet).

        This read never resets the attempt counter or mints a fresh code for an
        existing one - otherwise a patient screen that auto-refreshes would keep
        lifting the MAX_OTP_ATTEMPTS lockout and hand the nurse unlimited fresh
        try-windows. Recovering from a lockout is a deliberate action, handled
        by regenerate_completion_otp.

        Issued lazily here rather than at confirmation time because a
        Daily_Shift's shifts are confirmed by a bulk cascade that never loads
        the individual rows - and because bookings confirmed before this flow
        existed still need a code.
        """
        try:
            booking = self._get_visit_for_update(booking_id)
            if booking.patient_id != patient_id:
                # Deliberately the same answer as a missing booking, so this
                # can't be used to probe which booking ids exist.
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found."
                )
            self._assert_completable(booking)

            issued = booking.completion_otp is None
            if issued:
                booking.completion_otp = f"{secrets.randbelow(1_000_000):06d}"
                booking.completion_otp_attempts = 0
                self.db.commit()
            else:
                # Pure read - drop the row lock without writing.
                self.db.rollback()
        except Exception:
            self.db.rollback()
            raise

        if issued:
            self.db.refresh(booking)
        return booking

    def regenerate_completion_otp(
        self, *, booking_id: uuid.UUID, patient_id: uuid.UUID
    ) -> models.Booking:
        """
        Mints a fresh handover code and clears the attempt counter. This is the
        deliberate, patient-initiated way to recover after the nurse has burned
        the attempt budget on the previous code - a wrong code never changes the
        stored code, so the visit is only ever blocked, never lost.
        """
        try:
            booking = self._get_visit_for_update(booking_id)
            if booking.patient_id != patient_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found."
                )
            self._assert_completable(booking)

            booking.completion_otp = f"{secrets.randbelow(1_000_000):06d}"
            booking.completion_otp_attempts = 0
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(booking)
        return booking

    def complete_booking(
        self, *, booking_id: uuid.UUID, nurse_id: uuid.UUID, otp: str
    ) -> models.Booking:
        """
        Closes out a visit once the nurse supplies the code the patient read to
        them. This is the only path that produces a Completed booking.
        """
        try:
            booking = self._get_visit_for_update(booking_id)
            if booking.nurse_id != nurse_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found."
                )

            if booking.booking_status == "Completed":
                self.db.rollback()
                return booking  # idempotent: a retried request isn't an error

            self._assert_completable(booking)

            if booking.scheduled_start_time > datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This visit has not started yet and cannot be completed.",
                )

            if booking.completion_otp is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="No completion code has been issued for this booking. "
                           "Ask the patient to open the booking in their app.",
                )

            if booking.completion_otp_attempts >= self.MAX_OTP_ATTEMPTS:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many incorrect codes. Ask the patient to re-open the "
                           "booking in their app for a fresh code.",
                )

            otp_matched = secrets.compare_digest(booking.completion_otp, otp)
            if otp_matched:
                booking.booking_status = "Completed"
                booking.completion_otp = None  # single use
                booking.completion_otp_attempts = 0
            else:
                booking.completion_otp_attempts += 1

            # One commit either way - a wrong code still has to persist its
            # attempt, so the rejection below is raised after the write lands.
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        if not otp_matched:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect completion code.",
            )

        self.db.refresh(booking)
        return booking

    def _get_visit_for_update(self, booking_id: uuid.UUID) -> models.Booking:
        """Row-locks the booking, rejecting ids that don't exist."""
        booking = self.booking_repo.get_for_update(booking_id=booking_id)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found."
            )
        return booking

    def _assert_completable(self, booking: models.Booking) -> None:
        """
        A visit is closed out on the row that actually holds a time slot - a
        standalone Continuous booking, or one shift of a Daily_Shift parent.
        """
        if booking.is_parent_booking:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This booking is a multi-shift wrapper; each shift is "
                       "completed on its own.",
            )
        if booking.booking_status != "Confirmed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Booking is '{booking.booking_status}'; a handover code "
                       "applies only while a booking is Confirmed.",
            )

    # ------------------------------------------------------------------
    # Read-only lookups
    # ------------------------------------------------------------------
    def get_bookings_for_user(self, *, user_id: uuid.UUID) -> List[models.Booking]:
        return self.booking_repo.get_for_user(user_id=user_id)

    def list_all_bookings(self, *, skip: int = 0, limit: int = 100) -> List[models.Booking]:
        return self.booking_repo.list_all(skip=skip, limit=limit)

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
