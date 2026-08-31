# /views/notifications.py

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

import models
from config.database import get_db
from utils.roleChecker import RoleChecker
from services.notifications import NotificationService
from schemas.notifications import (
    NotificationCreate,
    NotificationResponse,
    UnreadCountResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Notifications"])

admin_dependency = Depends(RoleChecker(allowed_roles=["Admin"]))
user_dependency = Depends(RoleChecker(allowed_roles=["Admin", "Patient", "Nurse"]))


def get_notification_service(db: Session = Depends(get_db)) -> NotificationService:
    return NotificationService(db)


@router.post(
    "/admin/notifications",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a global/role/private notification (Admin Access)",
)
def create_notification(
    payload: NotificationCreate,
    current_user: models.User = admin_dependency,
    service: NotificationService = Depends(get_notification_service),
):
    try:
        return service.notify(
            type=payload.type,
            title=payload.title,
            body=payload.body,
            data=payload.data,
            audience_type=payload.audience_type,
            audience_role=payload.audience_role,
            target_user_id=payload.target_user_id,
            created_by=current_user.id,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to create notification")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create notification.",
        ) from exc


@router.get(
    "/notifications",
    response_model=List[NotificationResponse],
    status_code=status.HTTP_200_OK,
    summary="Get own notification feed",
)
def get_notifications(
    unread: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=100),
    before: Optional[datetime] = None,
    current_user: models.User = user_dependency,
    service: NotificationService = Depends(get_notification_service),
):
    try:
        return service.get_feed(
            user=current_user, unread=unread, limit=limit, before=before
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to retrieve notifications")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve notifications.",
        ) from exc


@router.patch(
    "/notifications/{notification_id}/read",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark a private notification as read",
)
def mark_notification_read(
    notification_id: uuid.UUID,
    current_user: models.User = user_dependency,
    service: NotificationService = Depends(get_notification_service),
):
    try:
        return service.mark_read(notification_id=notification_id, user=current_user)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to mark notification as read")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark notification as read.",
        ) from exc


@router.get(
    "/notifications/unread-count",
    response_model=UnreadCountResponse,
    status_code=status.HTTP_200_OK,
    summary="Count of unread private notifications",
)
def get_unread_count(
    current_user: models.User = user_dependency,
    service: NotificationService = Depends(get_notification_service),
):
    try:
        return UnreadCountResponse(
            unread_count=service.get_unread_count(user_id=current_user.id)
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to retrieve unread count")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve unread count.",
        ) from exc
