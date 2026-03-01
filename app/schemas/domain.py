"""
app/schemas/domain.py
Schémas Pydantic pour les domaines métier personnalisés.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DomainCreate(BaseModel):
    name: str
    description: Optional[str] = None


class DomainResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: Optional[str] = None
    is_system: bool
    created_at: datetime