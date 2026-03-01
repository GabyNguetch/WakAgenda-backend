"""
app/api/v1/endpoints/tasks.py
Routes CRUD complètes pour les tâches/événements (BF-11 à BF-15).
"""

import uuid
from typing import List, Optional
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.task import EventCategory, EventDomain, TaskStatus
from app.schemas.task import (
    TaskCreate, TaskUpdate, TaskResponse, TaskFilters, TaskStats
)
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["Tâches & Événements"])


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une nouvelle tâche",
)
def create_task(
    data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Crée une tâche et programme la notification si un rappel est défini (BF-11, BF-16)."""
    return TaskService(db).create_task(current_user.id, data)


@router.get(
    "",
    response_model=List[TaskResponse],
    summary="Lister les tâches (avec filtres)",
)
def list_tasks(
    category:  Optional[EventCategory]  = Query(None, description="Filtrer par catégorie"),
    domain:    Optional[EventDomain]    = Query(None, description="Filtrer par domaine"),
    status_q:  Optional[TaskStatus]     = Query(None, alias="status", description="Filtrer par statut"),
    date_from: Optional[date]           = Query(None, description="Date de début (YYYY-MM-DD)"),
    date_to:   Optional[date]           = Query(None, description="Date de fin (YYYY-MM-DD)"),
    skip: int  = Query(0,   ge=0,   description="Offset pagination"),
    limit: int = Query(100, ge=1, le=500, description="Limite pagination"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourne toutes les tâches avec filtres optionnels (BF-14)."""
    filters = TaskFilters(
        category=category,
        domain=domain,
        status=status_q,
        date_from=date_from,
        date_to=date_to,
    )
    return TaskService(db).list_tasks(current_user.id, filters, skip, limit)


@router.get(
    "/today",
    response_model=List[TaskResponse],
    summary="Tâches du jour",
)
def get_today_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourne les tâches planifiées aujourd'hui (BF-06)."""
    return TaskService(db).get_today_tasks(current_user.id)


@router.get(
    "/upcoming",
    response_model=List[TaskResponse],
    summary="Prochaines tâches",
)
def get_upcoming_tasks(
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourne les prochaines tâches planifiées (widget dashboard BF-08)."""
    return TaskService(db).get_upcoming_tasks(current_user.id, limit)


@router.get(
    "/stats",
    response_model=TaskStats,
    summary="Statistiques du tableau de bord",
)
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Indicateurs visuels pour le dashboard (BF-06, BF-07)."""
    return TaskService(db).get_stats(current_user.id)


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Détails d'une tâche",
)
def get_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return TaskService(db).get_task(task_id, current_user.id)


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Modifier une tâche",
)
def update_task(
    task_id: uuid.UUID,
    data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Modification partielle d'une tâche (BF-12)."""
    return TaskService(db).update_task(task_id, current_user.id, data)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer une tâche",
)
def delete_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Suppression d'une tâche et ses notifications associées (BF-13)."""
    TaskService(db).delete_task(task_id, current_user.id)
