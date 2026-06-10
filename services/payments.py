#services/payments.py
import uuid
from typing import List
from repositories.payments import PaymentRepository
from schemas.payments import PaymentCreate, PaymentUpdate, PaymentResponse
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

class PaymentService:
    """
    Service layer for handling business logic related to payments.
    """

    def __init__(self, db:Session):
        """
        Initializes the service with a databse session and a repositiory instance
        """
        self.db = db
        self.payment_repo = PaymentRepository(db)

    def create_payment(self, *,payment_in: PaymentCreate) -> PaymentResponse:
        """
        Creates a new payment record.

        Args:
            payment_in (PaymentCreate): The data for the new payment.

        Returns:
            PaymentResponse: The newly created payment object."""
        
        try:
            new_payment = self.payment_repo.create(payment_in)
            return PaymentResponse.model_validate(new_payment)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create payment record")
        

    def get_payment_by_id(self, *,payment_id: uuid.UUID) -> PaymentResponse:
        """
        Retrieves a payment by its ID.

        Args:
            payment_id (uuid.UUID): The ID of the payment to retrieve.

        Returns:
            PaymentResponse: The payment details if found.

        Raises:
            HTTPException: If the payment is not found.
        """
        payment = self.payment_repo.get_by_id(payment_id=payment_id)
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail = "Payment record not found for id: {payment_id}")
        return PaymentResponse.model_validate(payment)
    
    def get_payment_by_booking_id(self, *,booking_id: uuid.UUID) -> PaymentResponse:
        """
        Retrieves a payment by its booking ID.

        Args:
            booking_id (uuid.UUID): The ID of the booking for which to retrieve the payment.

        Returns:
            PaymentResponse: The payment details if found.

        Raises:
            HTTPException: If the payment is not found.
        """
        payment = self.payment_repo.get_by_booking_id(booking_id=booking_id)
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail = "Payment record not found for booking id: {booking_id}")
        return PaymentResponse.model_validate(payment)
    
    
    def get_payment_by_patient_id(self, *,patient_id: uuid.UUID) -> List[PaymentResponse]:
        """
        Retrieves all payments made by a specific patient.

        Args:
            patient_id (uuid.UUID): The ID of the patient.

        Returns:
            List[PaymentResponse]: A list of payment details for the patient.

        Raises:
            HTTPException: If no payments are found for the patient.
        """
        payments = self.payment_repo.get_by_patient_id(patient_id=patient_id)
        if not payments:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail = "No payment records found for patient id: {patient_id}")
        return [PaymentResponse.model_validate(payment) for payment in payments]


    def update_payment_status(self, *,payment_id: uuid.UUID, payment_update: PaymentUpdate) -> PaymentResponse:
        """
        Updates the status and other details of a payment record.

        Args:
            payment_id (uuid.UUID): The ID of the payment to update.
            payment_update (PaymentUpdate): The fields to update.
            
        Returns:
            PaymentResponse: The updated payment details.

        Raises:
            HTTPException: If the payment is not found.
        """
        payment = self.payment_repo.get_by_id(payment_id=payment_id)
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail = "Payment record not found for id: {payment_id}")
        update_data = payment_update.model_dump(exclude_unset=True)
        updated_payment = self.payment_repo.update(payment_id=payment_id, updates=update_data)
        return PaymentResponse.model_validate(updated_payment)
    
    def list_all_payments(self, *, skip: int = 0, limit: int = 100) -> List[PaymentResponse]:
        """
        Retrieves a list of all payments with pagination.

        Args:
            skip (int): The number of records to skip for pagination.
            limit (int): The maximum number of records to return.

        Returns:
            List[PaymentResponse]: A list of payment details.
        """
        payments = self.payment_repo.list_all(skip=skip, limit=limit)
        return [PaymentResponse.model_validate(payment) for payment in payments]
    
    def delete_payment(self, *,payment_id: uuid.UUID) -> PaymentResponse:
        """
        Deletes a payment record.

        Args:
            payment_id (uuid.UUID): The ID of the payment to delete.

        Returns:
            PaymentResponse: The details of the deleted payment.

        Raises:
            HTTPException: If the payment is not found.
        """
        payment = self.payment_repo.get_by_id(payment_id=payment_id)
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail = "Payment record not found for id: {payment_id}")
        deleted_payment = self.payment_repo.delete(payment_id=payment_id)
        if not deleted_payment:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail = "Failed to delete payment record for id: {payment_id}")
        return PaymentResponse.model_validate(deleted_payment)



