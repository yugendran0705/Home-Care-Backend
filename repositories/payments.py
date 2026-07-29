# /repositories/payments.py

import uuid
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import select

# Adjust the import path based on your project structure
import models
from schemas.payments import PaymentCreate # Assumes you will create this schema


class PaymentRepository:
    """
    Repository for handling all direct database operations for the Payment model.
    """

    def __init__(self, db: Session):
        """
        Initializes the repository with a database session.

        Args:
            db (Session): The SQLAlchemy database session.
        """
        self.db = db

    def create(self, *, payment_in: PaymentCreate) -> models.Payment:
        """
        Creates a new payment record. This is typically called when a booking
        is made and a payment is initiated.

        Args:
            payment_in (PaymentCreate): A Pydantic schema with the initial payment data.

        Returns:
            models.Payment: The newly created Payment ORM object.
        """
        # Create a Payment instance from the schema's model dump
        db_payment = models.Payment(**payment_in.model_dump())
        
        self.db.add(db_payment)
        self.db.commit()
        self.db.refresh(db_payment)
        return db_payment

    def get_by_id(self, *, payment_id: uuid.UUID) -> Optional[models.Payment]:
        """
        Retrieves a payment by its primary key (payment_id).

        Args:
            payment_id (uuid.UUID): The ID of the payment to retrieve.

        Returns:
            Optional[models.Payment]: The Payment object if found, otherwise None.
        """
        return self.db.get(models.Payment, payment_id)

    def get_by_booking_id(self, *, booking_id: uuid.UUID) -> Optional[models.Payment]:
        """
        Retrieves a payment associated with a specific booking ID.
        Since booking_id is unique, this should return at most one record.

        Args:
            booking_id (uuid.UUID): The booking's ID.

        Returns:
            Optional[models.Payment]: The associated Payment object, or None if not found.
        """
        statement = select(models.Payment).where(models.Payment.booking_id == booking_id)
        return self.db.execute(statement).scalar_one_or_none()

    def get_by_patient_id(self, *, patient_id: uuid.UUID) -> List[models.Payment]:
        """
        Retrieves all payments made by a specific patient.

        Args:
            patient_id (uuid.UUID): The patient's ID.

        Returns:
            List[models.Payment]: A list of all payments for that patient.
        """
        statement = select(models.Payment).where(models.Payment.patient_id == patient_id)
        return self.db.execute(statement).scalars().all()

    def get_by_gateway_order_id(self, *, gateway_order_id: str) -> Optional[models.Payment]:
        """
        Retrieves a payment by its Razorpay gateway order ID.

        Args:
            gateway_order_id (str): The Razorpay order ID.

        Returns:
            Optional[models.Payment]: The Payment object if found, otherwise None.
        """
        statement = select(models.Payment).where(models.Payment.gateway_order_id == gateway_order_id)
        return self.db.execute(statement).scalar_one_or_none()

    def update(self, *, payment_id: uuid.UUID, updates: Dict[str, Any]) -> Optional[models.Payment]:
        """
        Updates a payment record. This is useful for updating status,
        transaction ID, etc., after a payment gateway webhook or confirmation.

        Args:
            payment_id (uuid.UUID): The ID of the payment to update.
            updates (Dict[str, Any]): A dictionary of fields to update.

        Returns:
            Optional[models.Payment]: The updated Payment object, or None if not found.
        """
        db_payment = self.get_by_id(payment_id=payment_id)
        if not db_payment:
            return None
            
        for key, value in updates.items():
            setattr(db_payment, key, value)
            
        self.db.add(db_payment)
        self.db.commit()
        self.db.refresh(db_payment)
        return db_payment

    def list_all(self, *, skip: int = 0, limit: int = 100) -> List[models.Payment]:
        """
        Retrieves a paginated list of all payment records.
        Useful for admin dashboards.

        Args:
            skip (int): The number of records to skip.
            limit (int): The maximum number of records to return.

        Returns:
            List[models.Payment]: A list of Payment objects.
        """
        statement = select(models.Payment).offset(skip).limit(limit)
        return self.db.execute(statement).scalars().all()

    def delete(self, *, payment_id: uuid.UUID) -> Optional[models.Payment]:
        """
        Deletes a payment record from the database.
        Note: In a real-world scenario, you might prefer to soft-delete
        or change a status rather than hard-deleting payment records.

        Args:
            payment_id (uuid.UUID): The ID of the payment to delete.

        Returns:
            Optional[models.Payment]: The deleted Payment object, or None if not found.
        """
        db_payment = self.get_by_id(payment_id=payment_id)
        if not db_payment:
            return None
            
        self.db.delete(db_payment)
        self.db.commit()
        return db_payment
