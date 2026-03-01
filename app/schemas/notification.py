"""
app/schemas/notification.py
Schémas Pydantic pour les notifications.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.notification import NotificationType


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    task_id: Optional[uuid.UUID]
    title: str
    message: str
    notification_type: NotificationType
    is_read: bool
    scheduled_at: datetime
    created_at: datetime


class NotificationUpdate(BaseModel):
    is_read: bool = True


class UnreadCountResponse(BaseModel):
    unread_count: int
