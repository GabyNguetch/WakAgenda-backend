"""
app/services/notification_service.py
Logique métier pour les notifications.
"""

import uuid
from typing import List

from sqlalchemy.orm import Session

from app.repositories.notification_repository import NotificationRepository
from app.schemas.notification import NotificationResponse, UnreadCountResponse
from app.core.exceptions import NotFoundException


class NotificationService:
    def __init__(self, db: Session):
        self.notif_repo = NotificationRepository(db)

    def get_all(self, user_id: uuid.UUID, skip: int = 0, limit: int = 50) -> List[NotificationResponse]:
        notifs = self.notif_repo.get_all_for_user(user_id, skip, limit)
        return [NotificationResponse.model_validate(n) for n in notifs]

    def get_unread(self, user_id: uuid.UUID) -> List[NotificationResponse]:
        notifs = self.notif_repo.get_unread_for_user(user_id)
        return [NotificationResponse.model_validate(n) for n in notifs]

    def get_unread_count(self, user_id: uuid.UUID) -> UnreadCountResponse:
        count = self.notif_repo.count_unread(user_id)
        return UnreadCountResponse(unread_count=count)

    def mark_as_read(self, notif_id: uuid.UUID, user_id: uuid.UUID) -> NotificationResponse:
        notif = self.notif_repo.get_by_id_and_user(notif_id, user_id)
        if not notif:
            raise NotFoundException("Notification")
        notif = self.notif_repo.mark_as_read(notif)
        return NotificationResponse.model_validate(notif)

    def mark_all_as_read(self, user_id: uuid.UUID) -> dict:
        count = self.notif_repo.mark_all_as_read(user_id)
        return {"message": f"{count} notification(s) marquée(s) comme lue(s)."}

    def delete(self, notif_id: uuid.UUID, user_id: uuid.UUID) -> None:
        notif = self.notif_repo.get_by_id_and_user(notif_id, user_id)
        if not notif:
            raise NotFoundException("Notification")
        self.notif_repo.delete(notif)
