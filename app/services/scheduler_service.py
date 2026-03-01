"""
app/services/scheduler_service.py
Planificateur APScheduler :
  - Emails de rappel (J-1, -1h, -30min, -15min, -5min)
  - Email + notification in-app à l'heure de début
  - Mise à jour automatique du statut : LATE (début sans acceptation) → MISSED (fin sans acceptation)
"""

import uuid
import logging
from datetime import datetime, timedelta, timezone, date as date_type
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

from app.db.session import SessionLocal
from app.core.config import settings

log = logging.getLogger("wakagenda.scheduler")

# ── Singleton scheduler ────────────────────────────────────────────────────────
_scheduler: Optional[BackgroundScheduler] = None

# Minutes avant le début pour lesquelles on envoie un rappel
REMINDER_MINUTES = [1440, 60, 30, 15, 5]


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(
            jobstores={"default": MemoryJobStore()},
            executors={"default": ThreadPoolExecutor(max_workers=10)},
            job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300},
        )
    return _scheduler


def start_scheduler() -> None:
    sch = get_scheduler()
    if not sch.running:
        sch.start()
        log.info("Scheduler démarré.")


def shutdown_scheduler() -> None:
    sch = get_scheduler()
    if sch.running:
        sch.shutdown(wait=False)
        log.info("Scheduler arrêté.")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_action_urls(accept_token: str, cancel_token: str) -> tuple[str, str]:
    base = settings.APP_BASE_URL.rstrip("/")
    return (
        f"{base}/api/v1/tasks/action/accept/{accept_token}",
        f"{base}/api/v1/tasks/action/cancel/{cancel_token}",
    )


def _safe_remove_job(sch: BackgroundScheduler, job_id: str) -> None:
    """Supprime un job sans lever d'exception s'il n'existe pas."""
    try:
        sch.remove_job(job_id)
    except Exception:
        pass


# ── Jobs ───────────────────────────────────────────────────────────────────────

def _job_send_reminder(task_id: str, minutes_before: int) -> None:
    """Envoie l'email de rappel X minutes avant le début."""
    from app.models.task import Task, TaskStatus
    from app.services.email_service import email_service

    db = SessionLocal()
    try:
        task = db.get(Task, uuid.UUID(task_id))
        if not task or task.status in (TaskStatus.DONE, TaskStatus.CANCELLED, TaskStatus.MISSED):
            return

        accept_url, cancel_url = _make_action_urls(task.accept_token, task.cancel_token)
        email_service.send_reminder(
            to=task.user.email,
            first_name=task.user.first_name,
            task_title=task.title,
            task_date=task.task_date,
            start_time=task.start_time,
            end_time=task.end_time,
            category=task.category.value,
            domain=task.effective_domain_name,
            description=task.description,
            accept_url=accept_url,
            cancel_url=cancel_url,
            minutes_before=minutes_before,
        )
        log.info("Rappel %d min envoyé pour tâche %s", minutes_before, task_id)
    except Exception as exc:
        log.error("Erreur rappel tâche %s : %s", task_id, exc)
    finally:
        db.close()


def _job_send_start_notification(task_id: str) -> None:
    """Email de début + notification in-app + passage en IN_PROGRESS."""
    from app.models.task import Task, TaskStatus
    from app.models.notification import NotificationType
    from app.repositories.notification_repository import NotificationRepository
    from app.services.email_service import email_service

    db = SessionLocal()
    try:
        task = db.get(Task, uuid.UUID(task_id))
        if not task or task.status in (TaskStatus.DONE, TaskStatus.CANCELLED, TaskStatus.MISSED):
            return

        accept_url, cancel_url = _make_action_urls(task.accept_token, task.cancel_token)

        email_service.send_start_notification(
            to=task.user.email,
            first_name=task.user.first_name,
            task_title=task.title,
            task_date=task.task_date,
            start_time=task.start_time,
            end_time=task.end_time,
            category=task.category.value,
            domain=task.effective_domain_name,
            accept_url=accept_url,
            cancel_url=cancel_url,
        )

        NotificationRepository(db).create(
            user_id=task.user_id,
            task_id=task.id,
            title=f"Tâche en cours : {task.title}",
            message=(
                f"La tâche « {task.title} » a débuté à {task.start_time.strftime('%H:%M')}. "
                "Confirmez votre prise en charge."
            ),
            scheduled_at=datetime.now(timezone.utc),
            notification_type=NotificationType.REMINDER,
        )

        if task.status == TaskStatus.TODO:
            task.status = TaskStatus.IN_PROGRESS
            db.commit()

        log.info("Notification de début envoyée pour tâche %s", task_id)
    except Exception as exc:
        log.error("Erreur notification début tâche %s : %s", task_id, exc)
    finally:
        db.close()


def _job_check_late(task_id: str) -> None:
    """À l'heure de début (+ 5s) : si non acceptée → LATE."""
    from app.models.task import Task, TaskStatus

    db = SessionLocal()
    try:
        task = db.get(Task, uuid.UUID(task_id))
        if not task:
            return
        if task.accepted_at is None and task.status not in (
            TaskStatus.DONE, TaskStatus.CANCELLED, TaskStatus.MISSED
        ):
            task.status = TaskStatus.LATE
            db.commit()
            log.info("Tâche %s → EN RETARD", task_id)
    except Exception as exc:
        log.error("Erreur check_late tâche %s : %s", task_id, exc)
    finally:
        db.close()


def _job_check_missed(task_id: str) -> None:
    """À l'heure de fin : si toujours non acceptée → MISSED + notif."""
    from app.models.task import Task, TaskStatus
    from app.models.notification import NotificationType
    from app.repositories.notification_repository import NotificationRepository

    db = SessionLocal()
    try:
        task = db.get(Task, uuid.UUID(task_id))
        if not task:
            return
        if task.accepted_at is None and task.status not in (
            TaskStatus.DONE, TaskStatus.CANCELLED
        ):
            task.status = TaskStatus.MISSED
            db.commit()

            NotificationRepository(db).create(
                user_id=task.user_id,
                task_id=task.id,
                title=f"Tâche manquée : {task.title}",
                message=(
                    f"La tâche « {task.title} » est terminée sans confirmation. "
                    "Elle a été marquée comme manquée."
                ),
                scheduled_at=datetime.now(timezone.utc),
                notification_type=NotificationType.SYSTEM,
            )
            log.info("Tâche %s → MANQUÉE", task_id)
    except Exception as exc:
        log.error("Erreur check_missed tâche %s : %s", task_id, exc)
    finally:
        db.close()


# ── API publique ───────────────────────────────────────────────────────────────

def schedule_task_emails(
    task_id: uuid.UUID,
    task_date: date_type,
    start_time,
    end_time,
    accept_token: str,
    cancel_token: str,
) -> None:
    """Planifie tous les jobs email et de mise à jour de statut pour une tâche."""
    sch = get_scheduler()
    tid = str(task_id)
    now = datetime.now(timezone.utc)

    start_dt = datetime.combine(task_date, start_time).replace(tzinfo=timezone.utc)
    end_dt   = datetime.combine(task_date, end_time).replace(tzinfo=timezone.utc)

    # Emails de rappel (une entrée par délai)
    for minutes in REMINDER_MINUTES:
        run_at = start_dt - timedelta(minutes=minutes)
        if run_at > now:
            sch.add_job(
                _job_send_reminder,
                "date",
                run_date=run_at,
                args=[tid, minutes],
                id=f"reminder_{tid}_{minutes}",
                replace_existing=True,
            )

    # Email + notif au début de la tâche
    if start_dt > now:
        sch.add_job(
            _job_send_start_notification,
            "date",
            run_date=start_dt,
            args=[tid],
            id=f"start_{tid}",
            replace_existing=True,
        )

    # Vérification LATE (début + 5 secondes)
    if start_dt > now:
        sch.add_job(
            _job_check_late,
            "date",
            run_date=start_dt + timedelta(seconds=5),
            args=[tid],
            id=f"late_{tid}",
            replace_existing=True,
        )

    # Vérification MISSED (à l'heure de fin)
    if end_dt > now:
        sch.add_job(
            _job_check_missed,
            "date",
            run_date=end_dt,
            args=[tid],
            id=f"missed_{tid}",
            replace_existing=True,
        )


def cancel_task_jobs(task_id: uuid.UUID) -> None:
    """Annule tous les jobs planifiés pour une tâche donnée."""
    sch = get_scheduler()
    tid = str(task_id)

    # Jobs à préfixe simple
    for prefix in ("start_", "late_", "missed_"):
        _safe_remove_job(sch, f"{prefix}{tid}")

    # Jobs de rappel (un par délai)
    for minutes in REMINDER_MINUTES:
        _safe_remove_job(sch, f"reminder_{tid}_{minutes}")