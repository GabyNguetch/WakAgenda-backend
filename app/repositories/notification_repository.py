"""
app/repositories/notification_repository.py
Couche d'accès aux données pour les notifications.
"""

import uuid
from typing import List, Optional
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationType


class NotificationRepository:
    """Toutes les opérations DB relatives aux notifications."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, notif_id: uuid.UUID) -> Optional[Notification]:
        return self.db.get(Notification, notif_id)

    def get_by_id_and_user(self, notif_id: uuid.UUID, user_id: uuid.UUID) -> Optional[Notification]:
        return (
            self.db.query(Notification)
            .filter(Notification.id == notif_id, Notification.user_id == user_id)
            .first()
        )

    def get_all_for_user(self, user_id: uuid.UUID, skip: int = 0, limit: int = 50) -> List[Notification]:
        return (
            self.db.query(Notification)
            .filter(Notification.user_id == user_id)
            .order_by(Notification.scheduled_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_unread_for_user(self, user_id: uuid.UUID) -> List[Notification]:
        return (
            self.db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.is_read == False)
            .order_by(Notification.scheduled_at.desc())
            .all()
        )

    def count_unread(self, user_id: uuid.UUID) -> int:
        return (
            self.db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.is_read == False)
            .count()
        )

    def create(
        self,
        user_id: uuid.UUID,
        task_id: Optional[uuid.UUID],
        title: str,
        message: str,
        scheduled_at: datetime,
        notification_type: NotificationType = NotificationType.REMINDER,
    ) -> Notification:
        notif = Notification(
            user_id=user_id,
            task_id=task_id,
            title=title,
            message=message,
            notification_type=notification_type,
            scheduled_at=scheduled_at,
        )
        self.db.add(notif)
        self.db.commit()
        self.db.refresh(notif)
        return notif

    def mark_as_read(self, notif: Notification) -> Notification:
        notif.is_read = True
        self.db.commit()
        self.db.refresh(notif)
        return notif

    def mark_all_as_read(self, user_id: uuid.UUID) -> int:
        count = (
            self.db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.is_read == False)
            .update({"is_read": True})
        )
        self.db.commit()
        return count

    def delete(self, notif: Notification) -> None:
        self.db.delete(notif)
        self.db.commit()

    def delete_all_for_user(self, user_id: uuid.UUID) -> None:
        self.db.query(Notification).filter(Notification.user_id == user_id).delete()
        self.db.commit()
