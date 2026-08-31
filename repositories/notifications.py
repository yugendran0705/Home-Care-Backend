# /repositories/notifications.py

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_
from sqlalchemy.sql import func

import models


class NotificationRepository:
    """
    Repository for handling all direct database operations for the Notification model.
    """

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        *,
        type: str,
        title: str,
        body: str,
        data: dict,
        audience_type: str,
        audience_role: Optional[str],
        target_user_id: Optional[uuid.UUID],
        created_by: Optional[uuid.UUID],
    ) -> models.Notification:
        db_notification = models.Notification(
            type=type,
            title=title,
            body=body,
            data=data,
            audience_type=audience_type,
            audience_role=audience_role,
            target_user_id=target_user_id,
            created_by=created_by,
        )
        self.db.add(db_notification)
        self.db.commit()
        self.db.refresh(db_notification)
        return db_notification

    def get_by_id(self, *, notification_id: uuid.UUID) -> Optional[models.Notification]:
        return self.db.get(models.Notification, notification_id)

    def mark_read(self, *, notification: models.Notification) -> models.Notification:
        notification.read_at = func.now()
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def list_feed(
        self,
        *,
        user: models.User,
        unread: Optional[bool],
        limit: int,
        before: Optional[datetime],
    ) -> List[models.Notification]:
        audience_filter = or_(
            models.Notification.audience_type == "global",
            and_(
                models.Notification.audience_type == "role",
                models.Notification.audience_role == user.user_type,
            ),
            and_(
                models.Notification.audience_type == "user",
                models.Notification.target_user_id == user.id,
            ),
        )
        statement = select(models.Notification).where(audience_filter)

        if unread:
            statement = statement.where(models.Notification.read_at.is_(None))
        if before:
            statement = statement.where(models.Notification.created_at < before)

        statement = statement.order_by(models.Notification.created_at.desc()).limit(limit)
        return self.db.execute(statement).scalars().all()

    def count_unread_private(self, *, user_id: uuid.UUID) -> int:
        return (
            self.db.query(models.Notification)
            .filter(
                models.Notification.audience_type == "user",
                models.Notification.target_user_id == user_id,
                models.Notification.read_at.is_(None),
            )
            .count()
        )
