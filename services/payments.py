# services/payments.py

import uuid
import logging
from typing import List

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from repositories.payments import PaymentRepository
from services.bookings import BookingService
from schemas.payments import (
    PaymentCreate,
    PaymentUpdate,
    PaymentResponse,
    RazorpayOrderCreate,
    PaymentVerifyRequest,
    PaymentVerifyResponse,
)
from config.razorpay import get_razorpay_client, RAZORPAY_WEBHOOK_SECRET

logger = logging.getLogger(__name__)

razorpay_client = get_razorpay_client()


class PaymentService:
    """
    Service layer for handling business logic related to payments,
    including Razorpay order creation, checkout verification, and
    webhook processing.

    Note: there is no standalone create_payment(). create_order() is the
    only way a Payment row gets created — it always originates from a
    Razorpay order, so a payment can never exist without a
    gateway_order_id. Every downstream lookup (verify_checkout,
    webhook handling) relies on that invariant.
    """

    def __init__(self, db: Session, razorpay_client=razorpay_client):
        self.db = db
        self.payment_repo = PaymentRepository(db)
        self.booking_service = BookingService(db)

        self.razorpay = razorpay_client

    # ------------------------------------------------------------------
    # 1. Order creation — the only entry point for a new Payment row
    # ------------------------------------------------------------------

    def create_order(self, *, order_in: RazorpayOrderCreate) -> PaymentResponse:
        """
        Creates the internal Payment row (status=Initiated), then creates
        a matching order with Razorpay. If the gateway call fails, the
        local row is marked Failed rather than left dangling in
        Initiated forever.
        """
        payment_in = PaymentCreate(
            booking_id=order_in.booking_id,
            patient_id=order_in.patient_id,
            amount=order_in.amount,
            currency=order_in.currency,
        )

        try:
            payment = self.payment_repo.create(payment_in=payment_in)
        except Exception as e:
            logger.error(f"Failed to create local payment row for booking {order_in.booking_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initiate payment",
            )

        try:
            rp_order = self.razorpay.create_order(
                amount=order_in.amount,
                currency=order_in.currency,
                receipt=str(payment.id),
            )
        except Exception as e:
            logger.error(f"Razorpay order creation failed for payment {payment.id}: {e}")
            self.payment_repo.update(
                payment_id=payment.id,
                updates={
                    "payment_status": "Failed",
                    "failure_reason": "Gateway order creation failed",
                },
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not initiate payment with gateway",
            )

        updated_payment = self.payment_repo.update(
            payment_id=payment.id,
            updates={"gateway_order_id": rp_order["id"]},
        )

        return PaymentResponse(
            payment_id=updated_payment.id,
            razorpay_order_id=rp_order["id"],
            amount=updated_payment.amount,
            currency=updated_payment.currency,
            razorpay_key_id=self.razorpay.key_id,
        )

    # ------------------------------------------------------------------
    # 2. Client-side checkout verification (optimistic UI feedback only)
    # ------------------------------------------------------------------

    def verify_checkout(self, *, verify_in: PaymentVerifyRequest) -> PaymentVerifyResponse:
        """
        Verifies the signature returned by Razorpay Checkout in the
        browser. This gives fast UI feedback but is NOT the source of
        truth — the webhook handler is what finalizes payment state.
        """
        payment = self.payment_repo.get_by_gateway_order_id(
            gateway_order_id=verify_in.razorpay_order_id
        )
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No payment matches order id: {verify_in.razorpay_order_id}",
            )

        is_valid = self.razorpay.verify_payment_signature(
            order_id=verify_in.razorpay_order_id,
            payment_id=verify_in.razorpay_payment_id,
            signature=verify_in.razorpay_signature,
        )

        if is_valid:
            # Don't downgrade a payment the webhook already finalized
            # (e.g. don't stomp "Refunded" back to "Success").
            if payment.payment_status not in ("Success", "Refunded"):
                self.payment_repo.update(
                    payment_id=payment.id,
                    updates={
                        "payment_status": "Success",
                        "transaction_id": verify_in.razorpay_payment_id,
                    },
                )
        else:
            logger.warning(
                f"Signature verification failed for payment {payment.id} "
                f"(order {verify_in.razorpay_order_id})"
            )

        return PaymentVerifyResponse(
            payment_id=payment.id,
            payment_status="Success" if is_valid else payment.payment_status,
            verified=is_valid,
        )

    # ------------------------------------------------------------------
    # 3. Webhook handling (source of truth)
    # ------------------------------------------------------------------
    def handle_webhook(
            self,
            *,
            payload_body: bytes,
            signature: str,
            webhook_secret: str,
            parsed_payload: dict,
        ) -> None:
            """
            Verifies an inbound Razorpay webhook and applies it to the
            matching Payment/Booking. Idempotency comes from BookingService
            itself (confirm_booking/fail_booking already no-op on a booking
            that's not Pending) rather than a separate event-dedup table -
            Razorpay redeliveries are simply safe to reprocess.
            """
            if not self.razorpay.verify_webhook_signature(
                payload_body=payload_body,
                signature=signature,
                webhook_secret=webhook_secret,
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid webhook signature",
                )

            event_type = parsed_payload.get("event")
            payload = parsed_payload.get("payload", {})

            if not event_type:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Malformed webhook payload: missing event",
                )

            if event_type == "payment.captured":
                entity = payload.get("payment", {}).get("entity", {})
                order_id = entity.get("order_id")
                payment = self.payment_repo.get_by_gateway_order_id(gateway_order_id=order_id)
                if not payment:
                    logger.warning(f"Webhook payment.captured for unknown order_id={order_id}")
                    return
                self.booking_service.confirm_booking(
                    booking_id=payment.booking_id,
                    transaction_id=entity.get("id"),
                    payment_method=entity.get("method", "razorpay"),
                )

            elif event_type == "payment.failed":
                entity = payload.get("payment", {}).get("entity", {})
                order_id = entity.get("order_id")
                payment = self.payment_repo.get_by_gateway_order_id(gateway_order_id=order_id)
                if not payment:
                    logger.warning(f"Webhook payment.failed for unknown order_id={order_id}")
                    return
                self.payment_repo.update(
                    payment_id=payment.id,
                    updates={"failure_reason": entity.get("error_description")},
                )
                self.booking_service.fail_booking(
                    booking_id=payment.booking_id,
                    transaction_id=entity.get("id"),
                )

            else:
                logger.info(f"Ignoring unhandled webhook event type: {event_type}")

   
    # ------------------------------------------------------------------
    # Read / admin operations
    # ------------------------------------------------------------------

    def get_payment_by_id(self, *, payment_id: uuid.UUID) -> PaymentResponse:
        payment = self.payment_repo.get_by_id(payment_id=payment_id)
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment record not found for id: {payment_id}",
            )
        return PaymentResponse.model_validate(payment)

    def get_payment_by_booking_id(self, *, booking_id: uuid.UUID) -> PaymentResponse:
        payment = self.payment_repo.get_by_booking_id(booking_id=booking_id)
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment record not found for booking id: {booking_id}",
            )
        return PaymentResponse.model_validate(payment)

    def get_payment_by_patient_id(self, *, patient_id: uuid.UUID) -> List[PaymentResponse]:
        payments = self.payment_repo.get_by_patient_id(patient_id=patient_id)
        if not payments:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No payment records found for patient id: {patient_id}",
            )
        return [PaymentResponse.model_validate(payment) for payment in payments]

    def list_all_payments(self, *, skip: int = 0, limit: int = 100) -> List[PaymentResponse]:
        payments = self.payment_repo.list_all(skip=skip, limit=limit)
        return [PaymentResponse.model_validate(payment) for payment in payments]

    def delete_payment(self, *, payment_id: uuid.UUID) -> PaymentResponse:
        """
        Admin-only. Prefer this over letting payments be deleted freely —
        consider restricting this to non-Success statuses at the route
        level so a captured payment can't be hard-deleted, losing the
        financial record.
        """
        payment = self.payment_repo.get_by_id(payment_id=payment_id)
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment record not found for id: {payment_id}",
            )
        deleted_payment = self.payment_repo.delete(payment_id=payment_id)
        if not deleted_payment:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete payment record for id: {payment_id}",
            )
        return PaymentResponse.model_validate(deleted_payment)