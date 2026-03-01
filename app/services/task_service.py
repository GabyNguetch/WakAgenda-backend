"""
app/services/task_service.py
Logique métier pour les tâches.
Crée automatiquement des notifications et planifie les jobs email (BF-16).
"""

import uuid
from datetime import date, datetime, timedelta, timezone, time as dt_time
from typing import List, Optional

from sqlalchemy.orm import Session

from app.repositories.task_repository import TaskRepository
from app.repositories.notification_repository import NotificationRepository
from app.models.task import Task, ReminderDelay
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse, TaskStats, TaskFilters
from app.core.exceptions import NotFoundException, ForbiddenException


# Mapping délai de rappel → timedelta
REMINDER_DELTA: dict[ReminderDelay, timedelta] = {
    ReminderDelay.FIFTEEN_MIN: timedelta(minutes=15),
    ReminderDelay.THIRTY_MIN:  timedelta(minutes=30),
    ReminderDelay.ONE_HOUR:    timedelta(hours=1),
    ReminderDelay.DAY_BEFORE:  timedelta(days=1),
}


class TaskService:
    def __init__(self, db: Session):
        self.task_repo = TaskRepository(db)
        self.notif_repo = NotificationRepository(db)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _schedule_notification(self, task: Task) -> None:
        """Crée une notification in-app si un rappel est défini et les notifs activées."""
        if not task.reminder or not task.notification_enabled:
            return

        delta = REMINDER_DELTA[task.reminder]
        task_start_dt = datetime.combine(task.task_date, task.start_time).replace(
            tzinfo=timezone.utc
        )
        scheduled_at = task_start_dt - delta

        self.notif_repo.create(
            user_id=task.user_id,
            task_id=task.id,
            title=f"Rappel : {task.title}",
            message=(
                f"Votre tâche « {task.title} » commence le "
                f"{task.task_date.strftime('%d/%m/%Y')} à "
                f"{task.start_time.strftime('%H:%M')}."
            ),
            scheduled_at=scheduled_at,
        )

    @staticmethod
    def _schedule_emails(task: Task) -> None:
        """Planifie les jobs APScheduler pour les emails de rappel et de début."""
        from app.services.scheduler_service import schedule_task_emails
        if task.accept_token and task.cancel_token:
            schedule_task_emails(
                task_id=task.id,
                task_date=task.task_date,
                start_time=task.start_time,
                end_time=task.end_time,
                accept_token=task.accept_token,
                cancel_token=task.cancel_token,
            )

    @staticmethod
    def _cancel_emails(task_id: uuid.UUID) -> None:
        """Annule tous les jobs APScheduler liés à une tâche."""
        from app.services.scheduler_service import cancel_task_jobs
        cancel_task_jobs(task_id)

    # ── CRUD ───────────────────────────────────────────────────────────────────

    def create_task(self, user_id: uuid.UUID, data: TaskCreate) -> TaskResponse:
        task = self.task_repo.create(user_id, data)

        # Génération des tokens d'action email
        task.accept_token = str(uuid.uuid4())
        task.cancel_token = str(uuid.uuid4())
        self.task_repo.db.commit()
        self.task_repo.db.refresh(task)

        # Notification in-app
        self._schedule_notification(task)

        # Jobs email APScheduler
        self._schedule_emails(task)

        return TaskResponse.model_validate(task)

    def get_task(self, task_id: uuid.UUID, user_id: uuid.UUID) -> TaskResponse:
        task = self.task_repo.get_by_id_and_user(task_id, user_id)
        if not task:
            raise NotFoundException("Tâche")
        return TaskResponse.model_validate(task)

    def list_tasks(
        self,
        user_id: uuid.UUID,
        filters: TaskFilters,
        skip: int = 0,
        limit: int = 100,
    ) -> List[TaskResponse]:
        tasks = self.task_repo.get_all_for_user(
            user_id=user_id,
            category=filters.category,
            domain=filters.domain,
            status=filters.status,
            date_from=filters.date_from,
            date_to=filters.date_to,
            skip=skip,
            limit=limit,
        )
        return [TaskResponse.model_validate(t) for t in tasks]

    def get_today_tasks(self, user_id: uuid.UUID) -> List[TaskResponse]:
        tasks = self.task_repo.get_today_tasks(user_id)
        return [TaskResponse.model_validate(t) for t in tasks]

    def get_upcoming_tasks(self, user_id: uuid.UUID, limit: int = 5) -> List[TaskResponse]:
        tasks = self.task_repo.get_upcoming_tasks(user_id, limit)
        return [TaskResponse.model_validate(t) for t in tasks]

    def update_task(self, task_id: uuid.UUID, user_id: uuid.UUID, data: TaskUpdate) -> TaskResponse:
        task = self.task_repo.get_by_id_and_user(task_id, user_id)
        if not task:
            raise NotFoundException("Tâche")

        # Détecter si la planification temporelle change
        scheduling_fields = {"task_date", "start_time", "end_time"}
        update_data = data.model_dump(exclude_unset=True)
        scheduling_changed = bool(scheduling_fields & update_data.keys())

        task = self.task_repo.update(task, data)

        if scheduling_changed:
            # Annuler les anciens jobs et en créer de nouveaux
            self._cancel_emails(task.id)
            self._schedule_emails(task)

        return TaskResponse.model_validate(task)

    def delete_task(self, task_id: uuid.UUID, user_id: uuid.UUID) -> None:
        task = self.task_repo.get_by_id_and_user(task_id, user_id)
        if not task:
            raise NotFoundException("Tâche")

        # Annuler les jobs avant suppression
        self._cancel_emails(task.id)

        self.task_repo.delete(task)

    def get_stats(self, user_id: uuid.UUID) -> TaskStats:
        return self.task_repo.get_stats(user_id)