# services/payments.py

import uuid
from typing import List

from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from razorpay.errors import SignatureVerificationError

from repositories.payments import PaymentRepository
from services.bookings import BookingService
from schemas.payments import (
    PaymentCreate,
    PaymentUpdate,
    PaymentResponse,
    RazorpayOrderCreate,
    RazorpayOrderResponse,
    PaymentVerifyRequest,
    PaymentVerifyResponse,
)
from config.razorpay import get_razorpay_client, RAZORPAY_WEBHOOK_SECRET
from utils.logger import logger


class PaymentService:
    """
    Service layer for handling business logic related to payments,
    including Razorpay order creation, checkout verification, and
    webhook processing.

    There is no standalone create_payment() - a Payment row is only ever
    created alongside a Razorpay order, either here (create_order(), a
    generic entry point) or inline in BookingService.create_booking (the
    primary path: booking + payment + Razorpay order all happen together so
    the frontend gets everything it needs, in one response, to open Razorpay
    Checkout). Either path marks the row Failed rather than leaving it
    dangling in Initiated if the gateway call fails, so a Payment can exist
    without ever getting a gateway_order_id - verify_checkout/handle_webhook
    look payments up BY gateway_order_id, so such a row is simply
    unreachable from those paths rather than mishandled.
    """

    def __init__(self, db: Session, razorpay_client=None):
        self.db = db
        self.payment_repo = PaymentRepository(db)
        self.booking_service = BookingService(db)

        self.razorpay = razorpay_client or get_razorpay_client()

    # ------------------------------------------------------------------
    # 1. Order creation — the only entry point for a new Payment row
    # ------------------------------------------------------------------

    def create_order(self, *, order_in: RazorpayOrderCreate) -> RazorpayOrderResponse:
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
            rp_order = self.razorpay.order.create(
                data={
                    # Razorpay expects the amount as an integer in the
                    # currency's smallest unit (paise for INR), not rupees.
                    "amount": int(order_in.amount * 100),
                    "currency": order_in.currency,
                    "receipt": str(payment.id),
                }
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

        return RazorpayOrderResponse(
            payment_id=updated_payment.id,
            razorpay_order_id=rp_order["id"],
            amount=updated_payment.amount,
            currency=updated_payment.currency,
            razorpay_key_id=self.razorpay.auth[0],
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

        # The SDK raises SignatureVerificationError on a bad signature rather
        # than returning False.
        try:
            self.razorpay.utility.verify_payment_signature(
                {
                    "razorpay_order_id": verify_in.razorpay_order_id,
                    "razorpay_payment_id": verify_in.razorpay_payment_id,
                    "razorpay_signature": verify_in.razorpay_signature,
                }
            )
            is_valid = True
        except SignatureVerificationError:
            is_valid = False

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
            payload_body: str,
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

            payload_body must be the *raw* request body as sent by Razorpay
            (not re-serialized JSON) since the signature is an HMAC over
            those exact bytes.
            """
            # Raises SignatureVerificationError (not a bool False) on mismatch.
            try:
                self.razorpay.utility.verify_webhook_signature(
                    payload_body, signature, webhook_secret
                )
            except SignatureVerificationError:
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