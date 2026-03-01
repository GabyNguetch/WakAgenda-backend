"""
app/schemas/task.py
Schémas Pydantic pour les tâches/événements.
"""

import uuid
from datetime import date, time, datetime
from typing import Optional

from pydantic import BaseModel, field_validator, ConfigDict

from app.models.task import EventCategory, EventDomain, TaskStatus, ReminderDelay


# ── Création ───────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str
    task_date: date
    start_time: time
    end_time: time
    category: EventCategory = EventCategory.OTHER
    domain: str = "Technique"   
    status: TaskStatus = TaskStatus.TODO
    reminder: Optional[ReminderDelay] = None
    notification_enabled: bool = True
    description: Optional[str] = None

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, v: time, info) -> time:
        start = info.data.get("start_time")
        if start and v <= start:
            raise ValueError("L'heure de fin doit être postérieure à l'heure de début.")
        return v


# ── Mise à jour ────────────────────────────────────────────────────────────────

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    task_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    category: Optional[EventCategory] = None
    domain: Optional[str] = None
    status: Optional[TaskStatus] = None
    reminder: Optional[ReminderDelay] = None
    notification_enabled: Optional[bool] = None
    description: Optional[str] = None


# ── Réponse ────────────────────────────────────────────────────────────────────

class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    task_date: date
    start_time: time
    end_time: time
    category: EventCategory
    domain: str  # C'était EventDomain
    status: TaskStatus
    reminder: Optional[ReminderDelay]
    notification_enabled: bool
    description: Optional[str]
    created_at: datetime
    updated_at: datetime


# ── Filtres (query params) ─────────────────────────────────────────────────────

class TaskFilters(BaseModel):
    category: Optional[EventCategory] = None
    domain: Optional[str] = None
    status: Optional[TaskStatus] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None


# ── Statistiques (pour dashboard + rapport) ────────────────────────────────────

class TaskStats(BaseModel):
    total: int
    today: int
    overdue: int
    completed: int
    by_category: dict[str, int]
    by_status: dict[str, int]
    by_domain: dict[str, int]
