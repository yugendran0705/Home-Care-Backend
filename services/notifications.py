# services/notifications.py

import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models
from repositories.notifications import NotificationRepository
from utils.logger import logger
from utils.scheduling import APP_TZ


def _format_day(dt: datetime) -> str:
    """e.g. 'Sun, 20 Sep', in IST (the app's wall-clock zone)."""
    local = dt.astimezone(APP_TZ)
    return f"{local:%a}, {local.day} {local:%b}"


def _format_visit_time(dt: datetime) -> str:
    """e.g. 'Sun, 20 Sep at 5:30 PM', in IST."""
    local = dt.astimezone(APP_TZ)
    hour = local.hour % 12 or 12
    return f"{_format_day(dt)} at {hour}:{local:%M %p}"


def _booking_link(booking: models.Booking) -> dict:
    """
    `data` payload that lets the apps deep-link to the booking. A Daily_Shift
    shift also carries its parent, since the patient's detail screen is keyed
    on the parent booking.
    """
    data = {"booking_id": str(booking.id)}
    if booking.parent_booking_id is not None:
        data["parent_booking_id"] = str(booking.parent_booking_id)
    return data


class NotificationService:
    def __init__(self, db: Session):
        self.db = db
        self.notification_repo = NotificationRepository(db)

    def notify(
        self,
        type: str,
        title: str,
        body: str,
        data: Optional[dict] = None,
        *,
        audience_type: str,
        audience_role: Optional[str] = None,
        target_user_id: Optional[uuid.UUID] = None,
        created_by: Optional[uuid.UUID] = None,
    ) -> models.Notification:
        """
        Internal function called in-process by other services to create a
        notification. No event bus - direct call is sufficient at monolith scale.
        """
        if data is None:
            data = {}
        if audience_type == "role" and not audience_role:
            raise ValueError("audience_role is required when audience_type is 'role'")
        if audience_type == "user":
            if not target_user_id:
                raise ValueError(
                    "target_user_id is required when audience_type is 'user'"
                )
            target_user = self.db.get(models.User, target_user_id)
            if not target_user:
                raise ValueError("target_user_id does not reference an existing user")
            if audience_role and target_user.user_type != audience_role:
                raise ValueError("target_user's role does not match audience_role")

        return self.notification_repo.create(
            type=type,
            title=title,
            body=body,
            data=data,
            audience_type=audience_type,
            audience_role=audience_role,
            target_user_id=target_user_id,
            created_by=created_by,
        )

    # ------------------------------------------------------------------
    # Domain events. Called by other services right AFTER they commit their
    # own transaction: notify() commits on its own, so calling it mid-
    # transaction would commit the caller's half-finished work. Each one is
    # best-effort - a failed notification is logged and swallowed, never
    # allowed to fail (or roll back) the payment/booking/review it reports.
    # ------------------------------------------------------------------
    def _notify_user_safely(
        self, *, user_id: uuid.UUID, role: str, type: str, title: str, body: str, data: dict
    ) -> Optional[models.Notification]:
        try:
            return self.notify(
                type,
                title,
                body,
                data,
                audience_type="user",
                audience_role=role,
                target_user_id=user_id,
            )
        except Exception:
            self.db.rollback()
            logger.exception("Failed to send %s notification to user %s", type, user_id)
            return None

    def booking_confirmed(self, booking: models.Booking) -> None:
        """Patient: payment captured, booking (and all its shifts) confirmed."""
        nurse = booking.nurse
        service_name = booking.service.service_name
        first_day = _format_day(booking.scheduled_start_time)
        last_day = _format_day(booking.scheduled_end_time)
        if booking.is_parent_booking and first_day != last_day:
            when = f"daily from {first_day} to {last_day}"
        else:
            # A single visit, or a Daily_Shift booking with just one shift.
            when = f"on {_format_visit_time(booking.scheduled_start_time)}"
        self._notify_user_safely(
            user_id=booking.patient_id,
            role="Patient",
            type="booking_confirmed",
            title="Booking confirmed",
            body=f"{nurse.first_name} {nurse.last_name} will visit {when} for {service_name}.",
            data=_booking_link(booking),
        )

    def payment_failed(self, booking: models.Booking) -> None:
        """Patient: a payment attempt was declined; the booking is still held."""
        self._notify_user_safely(
            user_id=booking.patient_id,
            role="Patient",
            type="payment_failed",
            title="Payment didn't go through",
            body=(
                f"Your payment for {booking.service.service_name} was declined. "
                "Your slot is held for a short while - retry from the booking."
            ),
            data=_booking_link(booking),
        )

    def booking_cancelled(self, booking: models.Booking, *, reason: str) -> None:
        """Patient: the booking was cancelled (e.g. unpaid before expiry)."""
        self._notify_user_safely(
            user_id=booking.patient_id,
            role="Patient",
            type="booking_cancelled",
            title="Booking cancelled",
            body=f"Your {booking.service.service_name} booking was cancelled - {reason}.",
            data=_booking_link(booking),
        )

    def booking_cancelled_by_patient(
        self,
        booking: models.Booking,
        *,
        cancelled_visits: int,
        refund_amount: Decimal,
        was_paid: bool = True,
    ) -> None:
        """Patient: confirms their own cancellation and what's being refunded."""
        service_name = booking.service.service_name
        what = (
            f"your {service_name} booking"
            if cancelled_visits == 1
            else f"{cancelled_visits} upcoming visits of your {service_name} booking"
        )
        if not was_paid:
            refund = " No payment was taken."
        elif refund_amount > 0:
            refund = (
                f" A refund of ₹{refund_amount:,.2f} is on its way to your original "
                "payment method (usually 5-7 working days)."
            )
        else:
            refund = " No refund applies under the cancellation policy."
        self._notify_user_safely(
            user_id=booking.patient_id,
            role="Patient",
            type="booking_cancelled",
            title="Booking cancelled",
            body=f"You cancelled {what}.{refund}",
            data=_booking_link(booking),
        )

    def visits_cancelled_for_nurse(
        self, booking: models.Booking, *, cancelled_visits: List[models.Booking]
    ) -> None:
        """Nurse: a patient cancelled visits they were booked for."""
        if not cancelled_visits:
            return
        first = _format_visit_time(min(v.scheduled_start_time for v in cancelled_visits))
        count = len(cancelled_visits)
        service_name = booking.service.service_name
        if count == 1:
            what = f"their {service_name} visit on {first}. That slot is"
        else:
            what = f"{count} {service_name} visits starting {first}. Those slots are"
        self._notify_user_safely(
            user_id=booking.nurse_id,
            role="Nurse",
            type="booking_cancelled",
            title="Visit cancelled" if count == 1 else "Visits cancelled",
            body=f"{booking.patient.first_name} cancelled {what} free again.",
            data=_booking_link(booking),
        )

    def visit_completed(self, booking: models.Booking) -> None:
        """Patient: the nurse redeemed the handover code; ask for a review."""
        nurse = booking.nurse
        self._notify_user_safely(
            user_id=booking.patient_id,
            role="Patient",
            type="visit_completed",
            title=f"How was your visit with {nurse.first_name}?",
            body=(
                f"Your {booking.service.service_name} visit on "
                f"{_format_visit_time(booking.scheduled_start_time)} is complete. "
                "Rate your nurse to help others choose."
            ),
            data=_booking_link(booking),
        )

    def review_received(self, review: models.Review, booking: models.Booking) -> None:
        """Nurse: a patient reviewed one of their visits."""
        patient = booking.patient
        stars = "★" * review.rating + "☆" * (5 - review.rating)
        body = f"{patient.first_name} rated your {booking.service.service_name} visit {stars}"
        if review.comment:
            comment = review.comment if len(review.comment) <= 120 else review.comment[:117] + "..."
            body += f': "{comment}"'
        self._notify_user_safely(
            user_id=booking.nurse_id,
            role="Nurse",
            type="review_received",
            title=f"New {review.rating}-star review",
            body=body,
            data={**_booking_link(booking), "review_id": str(review.id)},
        )

    def get_feed(
        self,
        *,
        user: models.User,
        unread: Optional[bool],
        limit: int,
        before: Optional[datetime],
    ) -> List[models.Notification]:
        return self.notification_repo.list_feed(
            user=user, unread=unread, limit=limit, before=before
        )

    def mark_read(
        self, *, notification_id: uuid.UUID, user: models.User
    ) -> models.Notification:
        notification = self.notification_repo.get_by_id(notification_id=notification_id)
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
            )

        if notification.audience_type in ("global", "role"):
            return notification

        if notification.target_user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not your notification"
            )

        return self.notification_repo.mark_read(notification=notification)

    def get_unread_count(self, *, user_id: uuid.UUID) -> int:
        return self.notification_repo.count_unread_private(user_id=user_id)
