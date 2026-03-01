"""
app/schemas/user.py
Schémas Pydantic pour les utilisateurs.
Principe SOLID : Interface Segregation – schemas séparés par usage.
"""

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator, ConfigDict


# ── Schémas de base ────────────────────────────────────────────────────────────

class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    department: str
    supervisor_name: str
    internship_start_date: date


# ── Création (onboarding) ──────────────────────────────────────────────────────

class UserCreate(UserBase):
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Le mot de passe doit contenir au moins 6 caractères.")
        return v


# ── Mise à jour du profil ──────────────────────────────────────────────────────

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    department: Optional[str] = None
    supervisor_name: Optional[str] = None
    internship_start_date: Optional[date] = None
    profile_picture_url: Optional[str] = None


# ── Réponse publique (sans mot de passe) ──────────────────────────────────────

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    profile_picture_url: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


# ── Résumé léger (pour les relations) ─────────────────────────────────────────

class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str
    last_name: str
    email: EmailStr
    department: str
    profile_picture_url: Optional[str] = None
