"""
app/api/v1/endpoints/backup.py

Routes de sauvegarde et restauration complète de la base de données.
AUCUNE AUTHENTIFICATION REQUISE — à sécuriser côté réseau en production
(firewall, IP whitelist, ou variable d'env BACKUP_SECRET).

Routes :
  GET  /api/v1/backup/export   → CSV complet de toute la BDD (tous users, tâches, commentaires, domaines)
  POST /api/v1/backup/import   → Restauration depuis le CSV exporté

Format du CSV : une ligne par tâche, colonnes préfixées par table.
Les users et domaines manquants sont recréés à la volée.
"""

import csv
import io
import uuid
import logging
from datetime import date, time, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.task import Task, EventCategory, TaskStatus, ReminderDelay
from app.models.task_comment import TaskComment
from app.models.domain import Domain
from app.core.security import hash_password

log = logging.getLogger("wakagenda.backup")

router = APIRouter(prefix="/backup", tags=["Backup / Restore"])

# ── Colonnes du CSV de backup ──────────────────────────────────────────────────
BACKUP_FIELDS = [
    # ── User ──────────────────────────────────────────────────────────────────
    "user_id",
    "user_email",
    "user_first_name",
    "user_last_name",
    "user_department",
    "user_supervisor_name",
    "user_internship_start_date",
    "user_profile_picture_url",
    "user_is_active",
    "user_hashed_password",
    "user_created_at",

    # ── Task ──────────────────────────────────────────────────────────────────
    "task_id",
    "task_title",
    "task_date",
    "task_start_time",
    "task_end_time",
    "task_category",
    "task_domain",
    "task_status",
    "task_reminder",
    "task_notification_enabled",
    "task_description",
    "task_accept_token",
    "task_cancel_token",
    "task_accepted_at",
    "task_created_at",
    "task_updated_at",

    # ── TaskComment ────────────────────────────────────────────────────────────
    "comment_id",
    "comment_content",
    "comment_created_at",
    "comment_updated_at",

    # ── Domain (domaine personnalisé lié à la tâche) ──────────────────────────
    "domain_id",
    "domain_name",
    "domain_slug",
    "domain_description",
    "domain_is_system",
]


# ══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/export",
    summary="[BACKUP] Exporter toute la base de données en CSV",
    response_class=Response,
    responses={
        200: {
            "content": {"text/csv": {}},
            "description": "CSV complet de la base de données",
        }
    },
)
def backup_export(db: Session = Depends(get_db)):
    """
    Exporte TOUTE la base de données en un seul fichier CSV :
    - Tous les utilisateurs
    - Toutes leurs tâches
    - Les commentaires associés
    - Les domaines personnalisés liés

    Route NON protégée — à restreindre par firewall en production.
    """
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=BACKUP_FIELDS, quoting=csv.QUOTE_ALL)
    writer.writeheader()

    # Charger tous les users
    users: List[User] = db.query(User).order_by(User.created_at.asc()).all()

    for user in users:
        # Charger toutes les tâches du user
        tasks: List[Task] = (
            db.query(Task)
            .filter(Task.user_id == user.id)
            .order_by(Task.task_date.asc(), Task.start_time.asc())
            .all()
        )

        if not tasks:
            # Écrire quand même une ligne pour ne pas perdre le user
            writer.writerow(_user_row(user) | _empty_task_row())
            continue

        for task in tasks:
            # Commentaire
            comment: Optional[TaskComment] = (
                db.query(TaskComment)
                .filter(TaskComment.task_id == task.id)
                .first()
            )

            # Domaine personnalisé
            domain: Optional[Domain] = (
                db.query(Domain).filter(Domain.id == task.domain_id).first()
                if task.domain_id else None
            )

            writer.writerow(
                _user_row(user)
                | _task_row(task)
                | _comment_row(comment)
                | _domain_row(domain)
            )

    csv_bytes = ("\ufeff" + output.getvalue()).encode("utf-8")
    filename = f"wakagenda_backup_{date.today().isoformat()}.csv"

    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Helpers export ─────────────────────────────────────────────────────────────

def _user_row(user: User) -> dict:
    return {
        "user_id":                     str(user.id),
        "user_email":                  user.email,
        "user_first_name":             user.first_name,
        "user_last_name":              user.last_name,
        "user_department":             user.department,
        "user_supervisor_name":        user.supervisor_name,
        "user_internship_start_date":  user.internship_start_date.isoformat(),
        "user_profile_picture_url":    user.profile_picture_url or "",
        "user_is_active":              str(user.is_active),
        "user_hashed_password":        user.hashed_password,
        "user_created_at":             user.created_at.isoformat(),
    }


def _task_row(task: Task) -> dict:
    return {
        "task_id":                   str(task.id),
        "task_title":                task.title,
        "task_date":                 task.task_date.isoformat(),
        "task_start_time":           task.start_time.strftime("%H:%M:%S"),
        "task_end_time":             task.end_time.strftime("%H:%M:%S"),
        "task_category":             task.category.value if hasattr(task.category, "value") else str(task.category),
        "task_domain":               task.domain or "",
        "task_status":               task.status.value   if hasattr(task.status, "value")   else str(task.status),
        "task_reminder":             (task.reminder.value if hasattr(task.reminder, "value") else str(task.reminder)) if task.reminder else "",
        "task_notification_enabled": str(task.notification_enabled),
        "task_description":          task.description or "",
        "task_accept_token":         task.accept_token or "",
        "task_cancel_token":         task.cancel_token or "",
        "task_accepted_at":          task.accepted_at.isoformat() if task.accepted_at else "",
        "task_created_at":           task.created_at.isoformat(),
        "task_updated_at":           task.updated_at.isoformat(),
    }


def _empty_task_row() -> dict:
    return {f: "" for f in BACKUP_FIELDS if f.startswith("task_") or f.startswith("comment_") or f.startswith("domain_")}


def _comment_row(comment: Optional[TaskComment]) -> dict:
    if not comment:
        return {"comment_id": "", "comment_content": "", "comment_created_at": "", "comment_updated_at": ""}
    return {
        "comment_id":         str(comment.id),
        "comment_content":    comment.content,
        "comment_created_at": comment.created_at.isoformat(),
        "comment_updated_at": comment.updated_at.isoformat(),
    }


def _domain_row(domain: Optional[Domain]) -> dict:
    if not domain:
        return {"domain_id": "", "domain_name": "", "domain_slug": "", "domain_description": "", "domain_is_system": ""}
    return {
        "domain_id":          str(domain.id),
        "domain_name":        domain.name,
        "domain_slug":        domain.slug,
        "domain_description": domain.description or "",
        "domain_is_system":   str(domain.is_system),
    }


# ══════════════════════════════════════════════════════════════════════════════
# IMPORT / RESTORE
# ══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/import",
    summary="[RESTORE] Restaurer toute la base de données depuis un CSV de backup",
)
def backup_import(
    file: UploadFile = File(..., description="Fichier CSV généré par /backup/export"),
    db: Session = Depends(get_db),
):
    """
    Restaure la base depuis un CSV exporté par /backup/export.

    Stratégie (sans toucher aux données existantes) :
    - Users    : recréé si l'UUID est absent ; ignoré s'il existe déjà.
    - Domains  : recréé si l'UUID est absent ; ignoré s'il existe déjà.
    - Tasks    : recréée si l'UUID est absent ; ignorée si elle existe déjà.
    - Comments : upsert sur task_id (crée ou remplace).

    Retourne un résumé JSON.
    """
    raw  = file.file.read()
    text = raw.decode("utf-8-sig").strip()
    reader = csv.DictReader(io.StringIO(text))

    stats = {
        "users_created":    0,
        "users_skipped":    0,
        "domains_created":  0,
        "domains_skipped":  0,
        "tasks_created":    0,
        "tasks_skipped":    0,
        "comments_upserted": 0,
        "errors":           [],
    }

    # Cache en mémoire pour éviter les requêtes répétées
    seen_users:   dict[str, uuid.UUID] = {}   # email  → user.id
    seen_domains: dict[str, uuid.UUID] = {}   # domain_id(str) → domain.id réel

    for line_num, row in enumerate(reader, start=2):
        try:
            # ── 1. User ───────────────────────────────────────────────────────
            user_id_str = row.get("user_id", "").strip()
            user_email  = row.get("user_email", "").strip()

            if not user_email:
                continue  # ligne vide ou corrompue

            if user_email in seen_users:
                user_id = seen_users[user_email]
            else:
                user_id = _restore_user(db, row, stats)
                seen_users[user_email] = user_id

            # ── 2. Domain personnalisé ────────────────────────────────────────
            domain_id_str = row.get("domain_id", "").strip()
            real_domain_id: Optional[uuid.UUID] = None

            if domain_id_str:
                if domain_id_str in seen_domains:
                    real_domain_id = seen_domains[domain_id_str]
                else:
                    real_domain_id = _restore_domain(db, row, stats)
                    seen_domains[domain_id_str] = real_domain_id

            # ── 3. Task ───────────────────────────────────────────────────────
            task_id_str = row.get("task_id", "").strip()
            if not task_id_str:
                continue  # ligne user sans tâche

            new_task_id = _restore_task(db, row, user_id, real_domain_id, stats)

            # ── 4. Comment ────────────────────────────────────────────────────
            if new_task_id:
                _restore_comment(db, row, new_task_id, stats)

        except Exception as exc:
            stats["errors"].append(f"Ligne {line_num} : {exc}")
            log.error("Backup import ligne %d : %s", line_num, exc)

    db.commit()
    return stats


# ── Helpers import ─────────────────────────────────────────────────────────────

def _parse_bool(v: str) -> bool:
    return v.strip().lower() in ("true", "1", "yes", "oui")


def _find_enum(enum_class, value: str, default):
    for member in enum_class:
        if member.value == value or member.value.lower() == value.strip().lower():
            return member
    return default


def _restore_user(db: Session, row: dict, stats: dict) -> uuid.UUID:
    """Recrée le user s'il n'existe pas (vérifie par UUID ET par email)."""
    user_id_str = row.get("user_id", "").strip()
    email       = row.get("user_email", "").strip()

    # Chercher par UUID d'abord
    try:
        uid = uuid.UUID(user_id_str)
        existing = db.get(User, uid)
        if existing:
            stats["users_skipped"] += 1
            return existing.id
    except ValueError:
        uid = uuid.uuid4()

    # Chercher par email (au cas où l'UUID diffère)
    existing_by_email = db.query(User).filter(User.email == email).first()
    if existing_by_email:
        stats["users_skipped"] += 1
        return existing_by_email.id

    # Créer le user
    hashed_pw = row.get("user_hashed_password", "").strip()
    if not hashed_pw:
        hashed_pw = hash_password("WakAgenda2025!")  # mot de passe temporaire

    try:
        internship_start = date.fromisoformat(row.get("user_internship_start_date", date.today().isoformat()))
    except ValueError:
        internship_start = date.today()

    new_user = User(
        id=uid,
        email=email,
        first_name=row.get("user_first_name", ""),
        last_name=row.get("user_last_name", ""),
        department=row.get("user_department", ""),
        supervisor_name=row.get("user_supervisor_name", ""),
        internship_start_date=internship_start,
        profile_picture_url=row.get("user_profile_picture_url") or None,
        is_active=_parse_bool(row.get("user_is_active", "True")),
        hashed_password=hashed_pw,
    )
    db.add(new_user)
    db.flush()
    stats["users_created"] += 1
    return new_user.id


def _restore_domain(db: Session, row: dict, stats: dict) -> Optional[uuid.UUID]:
    """Recrée le domaine personnalisé s'il n'existe pas."""
    import re

    domain_id_str = row.get("domain_id", "").strip()
    domain_name   = row.get("domain_name", "").strip()

    if not domain_name:
        return None

    try:
        did = uuid.UUID(domain_id_str)
        existing = db.get(Domain, did)
        if existing:
            stats["domains_skipped"] += 1
            return existing.id
    except ValueError:
        did = uuid.uuid4()

    # Chercher par nom
    existing_by_name = db.query(Domain).filter(Domain.name.ilike(domain_name)).first()
    if existing_by_name:
        stats["domains_skipped"] += 1
        return existing_by_name.id

    # Générer slug
    slug = domain_name.lower().strip()
    for fr, en in [("à","a"),("â","a"),("é","e"),("è","e"),("ê","e"),("î","i"),("ô","o"),("û","u"),("ç","c")]:
        slug = slug.replace(fr, en)
    slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")

    # S'assurer de l'unicité du slug
    base_slug = slug
    counter   = 1
    while db.query(Domain).filter(Domain.slug == slug).first():
        slug = f"{base_slug}_{counter}"
        counter += 1

    new_domain = Domain(
        id=did,
        name=domain_name,
        slug=slug,
        description=row.get("domain_description") or None,
        is_system=_parse_bool(row.get("domain_is_system", "False")),
    )
    db.add(new_domain)
    db.flush()
    stats["domains_created"] += 1
    return new_domain.id


def _restore_task(
    db: Session,
    row: dict,
    user_id: uuid.UUID,
    domain_id: Optional[uuid.UUID],
    stats: dict,
) -> Optional[uuid.UUID]:
    """Recrée la tâche si elle n'existe pas déjà (vérification par UUID)."""
    task_id_str = row.get("task_id", "").strip()

    try:
        tid = uuid.UUID(task_id_str)
        existing = db.get(Task, tid)
        if existing:
            stats["tasks_skipped"] += 1
            return existing.id
    except ValueError:
        tid = uuid.uuid4()

    try:
        task_date  = date.fromisoformat(row["task_date"])
        start_time = time.fromisoformat(row["task_start_time"])
        end_time   = time.fromisoformat(row["task_end_time"])
    except (KeyError, ValueError) as exc:
        raise ValueError(f"Champs date/heure invalides : {exc}")

    category = _find_enum(EventCategory, row.get("task_category", ""), EventCategory.OTHER)
    status   = _find_enum(TaskStatus,    row.get("task_status", ""),   TaskStatus.TODO)

    reminder_str = row.get("task_reminder", "").strip()
    reminder = _find_enum(ReminderDelay, reminder_str, None) if reminder_str else None

    # Tokens (peuvent être vides si la BDD a été reconstituée)
    accept_token = row.get("task_accept_token", "").strip() or str(uuid.uuid4())
    cancel_token = row.get("task_cancel_token", "").strip() or str(uuid.uuid4())

    # Vérifier unicité des tokens (contrainte unique en BDD)
    if db.query(Task).filter(Task.accept_token == accept_token).first():
        accept_token = str(uuid.uuid4())
    if db.query(Task).filter(Task.cancel_token == cancel_token).first():
        cancel_token = str(uuid.uuid4())

    accepted_at_str = row.get("task_accepted_at", "").strip()
    accepted_at = None
    if accepted_at_str:
        try:
            accepted_at = datetime.fromisoformat(accepted_at_str)
        except ValueError:
            pass

    new_task = Task(
        id=tid,
        user_id=user_id,
        title=row.get("task_title", "Sans titre"),
        task_date=task_date,
        start_time=start_time,
        end_time=end_time,
        category=category,
        domain=row.get("task_domain", "Technique") or "Technique",
        status=status,
        reminder=reminder,
        notification_enabled=_parse_bool(row.get("task_notification_enabled", "True")),
        description=row.get("task_description") or None,
        accept_token=accept_token,
        cancel_token=cancel_token,
        accepted_at=accepted_at,
        domain_id=domain_id,
    )
    db.add(new_task)
    db.flush()
    stats["tasks_created"] += 1
    return new_task.id


def _restore_comment(
    db: Session,
    row: dict,
    task_id: uuid.UUID,
    stats: dict,
) -> None:
    """Upsert du commentaire lié à la tâche."""
    content = row.get("comment_content", "").strip()
    if not content:
        return

    existing = db.query(TaskComment).filter(TaskComment.task_id == task_id).first()
    if existing:
        existing.content = content
        existing.updated_at = datetime.now(timezone.utc)
    else:
        comment_id_str = row.get("comment_id", "").strip()
        try:
            cid = uuid.UUID(comment_id_str)
            # Vérifier que cet UUID n'est pas déjà utilisé
            if db.get(TaskComment, cid):
                cid = uuid.uuid4()
        except ValueError:
            cid = uuid.uuid4()

        new_comment = TaskComment(
            id=cid,
            task_id=task_id,
            content=content,
        )
        db.add(new_comment)

    db.flush()
    stats["comments_upserted"] += 1