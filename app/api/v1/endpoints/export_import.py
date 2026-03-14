"""
app/api/v1/endpoints/export_import.py
Routes :
  GET  /api/v1/export/csv   — Export CSV de toutes les tâches de l'utilisateur
  POST /api/v1/import/csv   — Import/Restore CSV de tâches
"""

import csv
import io
import uuid
from datetime import date, time, datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.task import Task, EventCategory, TaskStatus, ReminderDelay
from app.repositories.task_repository import TaskRepository
from app.repositories.task_comment_repository import TaskCommentRepository

router = APIRouter(tags=["Export / Import"])

CSV_FIELDS = [
    "id", "title", "date", "start_time", "end_time",
    "category", "domain", "status",
    "reminder", "notification_enabled", "description",
    "comment_content", "created_at", "updated_at",
]


# ── Fonctionnalité 4 — Export CSV ─────────────────────────────────────────────

@router.get(
    "/export/csv",
    summary="Exporter toutes les tâches en CSV (compatible Excel)",
    response_class=Response,
    responses={
        200: {
            "content": {"text/csv": {}},
            "description": "Fichier CSV généré",
        }
    },
)
def export_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Génère un fichier CSV UTF-8 BOM de toutes les tâches de l'utilisateur.
    Colonnes : id, title, date, start_time, end_time, category, domain, status,
               reminder, notification_enabled, description, comment_content,
               created_at, updated_at.
    """
    task_repo    = TaskRepository(db)
    comment_repo = TaskCommentRepository(db)

    tasks = task_repo.get_all_for_user(user_id=current_user.id, limit=100_000)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, quoting=csv.QUOTE_ALL)
    writer.writeheader()

    for task in tasks:
        comment = comment_repo.get_by_task_id(task.id)
        writer.writerow({
            "id":                   str(task.id),
            "title":                task.title,
            "date":                 task.task_date.isoformat(),
            "start_time":           task.start_time.strftime("%H:%M:%S"),
            "end_time":             task.end_time.strftime("%H:%M:%S"),
            "category":             task.category.value if hasattr(task.category, "value") else str(task.category),
            "domain":               task.domain,
            "status":               task.status.value   if hasattr(task.status, "value")   else str(task.status),
            "reminder":             (task.reminder.value if hasattr(task.reminder, "value") else str(task.reminder)) if task.reminder else "",
            "notification_enabled": str(task.notification_enabled),
            "description":          task.description or "",
            "comment_content":      comment.content if comment else "",
            "created_at":           task.created_at.isoformat(),
            "updated_at":           task.updated_at.isoformat(),
        })

    # UTF-8 BOM pour compatibilité Excel
    csv_bytes = ("\ufeff" + output.getvalue()).encode("utf-8")

    filename = f"wakagenda_export_{current_user.id}_{date.today().isoformat()}.csv"
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Fonctionnalité 5 — Import CSV ─────────────────────────────────────────────

def _parse_bool(value: str) -> bool:
    return value.strip().lower() in ("true", "1", "yes", "oui")


def _parse_optional_str(value: str) -> str | None:
    stripped = value.strip()
    return stripped if stripped else None


def _find_enum_value(enum_class, value: str):
    """Cherche la valeur d'enum par .value (insensible à la casse)."""
    for member in enum_class:
        if member.value == value or member.value.lower() == value.lower():
            return member
    return None


@router.post(
    "/import/csv",
    summary="Importer des tâches depuis un fichier CSV (même format que l'export)",
)
def import_csv(
    file: UploadFile = File(..., description="Fichier .csv au format WakAgenda"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Restaure les tâches depuis un CSV exporté par /export/csv.
    - Les tâches existantes (même id) sont ignorées (skip).
    - Les nouvelles tâches sont créées avec un nouvel id auto-généré.
    - Les commentaires non vides sont insérés/mis à jour via upsert.
    Retourne : { imported, skipped, errors }
    """
    task_repo    = TaskRepository(db)
    comment_repo = TaskCommentRepository(db)

    # Lire le contenu du fichier uploadé
    raw = file.file.read()
    # Supprimer le BOM éventuel
    text = raw.decode("utf-8-sig").strip()

    reader = csv.DictReader(io.StringIO(text))

    imported = 0
    skipped  = 0
    errors: List[str] = []

    for line_num, row in enumerate(reader, start=2):
        try:
            # Vérifier si la tâche existe déjà (par id)
            try:
                original_id = uuid.UUID(row["id"])
            except (ValueError, KeyError):
                original_id = None

            if original_id:
                existing = task_repo.get_by_id_and_user(original_id, current_user.id)
                if existing:
                    skipped += 1
                    continue

            # Parsing des champs obligatoires
            title      = row["title"].strip()
            task_date  = date.fromisoformat(row["date"])
            start_time = time.fromisoformat(row["start_time"])
            end_time   = time.fromisoformat(row["end_time"])

            # Enums
            category = _find_enum_value(EventCategory, row.get("category", "Autre")) or EventCategory.OTHER
            status   = _find_enum_value(TaskStatus,    row.get("status", "À faire"))  or TaskStatus.TODO

            reminder_str = row.get("reminder", "").strip()
            reminder = _find_enum_value(ReminderDelay, reminder_str) if reminder_str else None

            notification_enabled = _parse_bool(row.get("notification_enabled", "True"))
            description  = _parse_optional_str(row.get("description", ""))
            comment_html = _parse_optional_str(row.get("comment_content", ""))
            domain       = row.get("domain", "Technique").strip() or "Technique"

            # Créer la tâche (nouvel id auto-généré par la BDD)
            new_task = Task(
                user_id=current_user.id,
                title=title,
                task_date=task_date,
                start_time=start_time,
                end_time=end_time,
                category=category,
                domain=domain,
                status=status,
                reminder=reminder,
                notification_enabled=notification_enabled,
                description=description,
            )
            db.add(new_task)
            db.flush()  # Pour obtenir l'id généré

            # Commentaire associé
            if comment_html:
                comment_repo.upsert(new_task.id, comment_html)

            imported += 1

        except Exception as exc:
            errors.append(f"Ligne {line_num} : {str(exc)}")

    db.commit()

    return {
        "imported": imported,
        "skipped":  skipped,
        "errors":   errors,
    }