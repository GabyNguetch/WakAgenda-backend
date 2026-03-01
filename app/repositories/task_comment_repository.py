"""
app/repositories/task_comment_repository.py
Couche d'accès aux données pour les commentaires de tâche.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.task_comment import TaskComment


class TaskCommentRepository:
    """Opérations DB pour les commentaires (1 par tâche, upsert)."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_task_id(self, task_id: uuid.UUID) -> Optional[TaskComment]:
        return (
            self.db.query(TaskComment)
            .filter(TaskComment.task_id == task_id)
            .first()
        )

    def upsert(self, task_id: uuid.UUID, content: str) -> TaskComment:
        """Crée le commentaire s'il n'existe pas, le remplace sinon."""
        comment = self.get_by_task_id(task_id)
        if comment is None:
            comment = TaskComment(task_id=task_id, content=content)
            self.db.add(comment)
        else:
            comment.content = content
            comment.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(comment)
        return comment

    def delete_by_task_id(self, task_id: uuid.UUID) -> None:
        comment = self.get_by_task_id(task_id)
        if comment:
            self.db.delete(comment)
            self.db.commit()