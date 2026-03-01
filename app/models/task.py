"""
app/models/task.py
Modèle SQLAlchemy – Table tasks.
"""

import uuid
from datetime import date, time, datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import String, Date, Time, DateTime, Boolean, Text, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base_class import Base


class EventCategory(str, PyEnum):
    MEETING    = "Réunion"
    DEVELOPMENT = "Développement"
    TRAINING   = "Formation"
    DELIVERABLE = "Rendu"
    OTHER      = "Autre"


class EventDomain(str, PyEnum):
    TECHNICAL      = "Technique"
    ADMINISTRATIVE = "Administratif"
    COMMERCIAL     = "Commercial"
    TRANSVERSAL    = "Transversal"


class TaskStatus(str, PyEnum):
    TODO        = "À faire"
    IN_PROGRESS = "En cours"
    DONE        = "Terminé"
    CANCELLED   = "Annulé"
    LATE        = "En retard"
    MISSED      = "Manquée"


class ReminderDelay(str, PyEnum):
    FIFTEEN_MIN = "15 min avant"
    THIRTY_MIN  = "30 min avant"
    ONE_HOUR    = "1 heure avant"
    DAY_BEFORE  = "La veille"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    title:      Mapped[str]  = mapped_column(String(255), nullable=False)
    task_date:  Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time:   Mapped[time] = mapped_column(Time, nullable=False)

    category: Mapped[EventCategory] = mapped_column(
        Enum(EventCategory, name="event_category"),
        nullable=False, default=EventCategory.OTHER
    )
    # MODIFICATION ICI : Remplacez l'Enum par String
    domain: Mapped[str] = mapped_column(String(100), nullable=False) 
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status"),
        nullable=False, default=TaskStatus.TODO
    )

    reminder: Mapped[ReminderDelay | None] = mapped_column(
        Enum(ReminderDelay, name="reminder_delay"), nullable=True
    )
    notification_enabled: Mapped[bool]     = mapped_column(Boolean, default=True)
    description:          Mapped[str | None] = mapped_column(Text, nullable=True)

    # Champs actions email
    accept_token: Mapped[str | None] = mapped_column(
        String(36), nullable=True, unique=True, index=True
    )
    cancel_token: Mapped[str | None] = mapped_column(
        String(36), nullable=True, unique=True, index=True
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Domaine personnalisé
    domain_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("domains.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relations ──────────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(  # noqa: F821
        "User", back_populates="tasks"
    )
    notifications: Mapped[list["Notification"]] = relationship(  # noqa: F821
        "Notification", back_populates="task", cascade="all, delete-orphan"
    )
    custom_domain: Mapped["Domain | None"] = relationship(  # noqa: F821
        "Domain", back_populates="tasks", foreign_keys=[domain_id]
    )
    comments: Mapped[list["TaskComment"]] = relationship(  # noqa: F821
        "TaskComment", back_populates="task", cascade="all, delete-orphan"
    )

    # ── Propriété calculée ─────────────────────────────────────────────────────
    @property
    def effective_domain_name(self) -> str:
        if self.custom_domain is not None:
            return self.custom_domain.name
        return self.domain.value