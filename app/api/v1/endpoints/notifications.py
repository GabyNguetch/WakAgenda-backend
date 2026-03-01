"""
app/api/v1/endpoints/notifications.py
Routes pour la gestion des notifications (BF-16 à BF-18).
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.notification import NotificationResponse, UnreadCountResponse
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get(
    "",
    response_model=List[NotificationResponse],
    summary="Toutes les notifications",
)
def get_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourne toutes les notifications de l'utilisateur (BF-16)."""
    return NotificationService(db).get_all(current_user.id, skip, limit)


@router.get(
    "/unread",
    response_model=List[NotificationResponse],
    summary="Notifications non lues",
)
def get_unread_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourne les notifications non lues (BF-17)."""
    return NotificationService(db).get_unread(current_user.id)


@router.get(
    "/unread/count",
    response_model=UnreadCountResponse,
    summary="Compteur de notifications non lues",
)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Badge du compteur notifications (BF-17)."""
    return NotificationService(db).get_unread_count(current_user.id)


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Marquer une notification comme lue",
)
def mark_as_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Marque une notification individuelle comme lue (BF-18)."""
    return NotificationService(db).mark_as_read(notification_id, current_user.id)


@router.patch(
    "/read-all",
    summary="Marquer toutes les notifications comme lues",
)
def mark_all_as_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Marque toutes les notifications comme lues en masse (BF-18)."""
    return NotificationService(db).mark_all_as_read(current_user.id)


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une notification",
)
def delete_notification(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    NotificationService(db).delete(notification_id, current_user.id)
