"""
app/api/v1/endpoints/task_comments.py
Routes pour les commentaires de tâche (1 commentaire par tâche terminée).
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.task_comment import TaskCommentCreate, TaskCommentResponse
from app.services.task_comment_service import TaskCommentService

router = APIRouter(tags=["Commentaires de tâche"])


@router.post(
    "/tasks/{task_id}/comment",
    response_model=TaskCommentResponse,
    status_code=status.HTTP_200_OK,
    summary="Soumettre ou remplacer le commentaire d'une tâche terminée",
)
def submit_comment(
    task_id: uuid.UUID,
    data: TaskCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskCommentResponse:
    """
    Crée ou remplace le commentaire d'une tâche.
    La tâche doit être au statut DONE (BF commentaire).
    """
    return TaskCommentService(db).submit_comment(task_id, current_user.id, data)


@router.get(
    "/tasks/{task_id}/comment",
    response_model=Optional[TaskCommentResponse],
    summary="Récupérer le commentaire d'une tâche",
)
def get_comment(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Optional[TaskCommentResponse]:
    """Retourne le commentaire de la tâche, ou null si absent."""
    return TaskCommentService(db).get_comment(task_id, current_user.id)