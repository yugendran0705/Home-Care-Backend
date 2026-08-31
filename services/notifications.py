# services/notifications.py

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models
from repositories.notifications import NotificationRepository


class NotificationService:
    def __init__(self, db: Session):
        self.db = db
        self.notification_repo = NotificationRepository(db)

    def notify(
        self,
        type: str,
        title: str,
        body: str,
        data: dict = {},
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
