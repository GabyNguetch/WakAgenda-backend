"""
app/services/task_comment_service.py
Logique métier pour les commentaires de tâche.
"""

import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.task_repository import TaskRepository
from app.repositories.task_comment_repository import TaskCommentRepository
from app.schemas.task_comment import TaskCommentCreate, TaskCommentResponse
from app.models.task import TaskStatus
from app.core.exceptions import NotFoundException, ForbiddenException


class TaskCommentService:
    def __init__(self, db: Session):
        self.task_repo    = TaskRepository(db)
        self.comment_repo = TaskCommentRepository(db)

    def submit_comment(
        self,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
        data: TaskCommentCreate,
    ) -> TaskCommentResponse:
        """
        Crée ou remplace le commentaire d'une tâche.
        Règles métier :
          - La tâche doit appartenir à l'utilisateur courant.
          - La tâche doit être au statut DONE.
        """
        task = self.task_repo.get_by_id(task_id)
        if not task:
            raise NotFoundException("Tâche")

        if task.user_id != user_id:
            raise ForbiddenException("Vous n'êtes pas autorisé à commenter cette tâche.")

        if task.status != TaskStatus.DONE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La tâche doit être terminée pour être commentée.",
            )

        comment = self.comment_repo.upsert(task_id, data.content)
        return TaskCommentResponse.model_validate(comment)

    def get_comment(
        self,
        task_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[TaskCommentResponse]:
        """
        Retourne le commentaire d'une tâche.
        Vérifie que la tâche appartient à l'utilisateur.
        """
        task = self.task_repo.get_by_id(task_id)
        if not task:
            raise NotFoundException("Tâche")

        if task.user_id != user_id:
            raise ForbiddenException("Accès refusé.")

        comment = self.comment_repo.get_by_task_id(task_id)
        if not comment:
            return None
        return TaskCommentResponse.model_validate(comment)