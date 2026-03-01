"""
app/schemas/task_comment.py
Schémas Pydantic pour les commentaires de tâche.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class TaskCommentCreate(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Le commentaire ne peut pas être vide.")
        return v


class TaskCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    content: str
    created_at: datetime
    updated_at: datetime