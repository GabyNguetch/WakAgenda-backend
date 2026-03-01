"""
app/services/user_service.py
Logique métier pour les utilisateurs.
"""

import uuid
import os
import shutil
from pathlib import Path

from sqlalchemy.orm import Session
from fastapi import UploadFile

from app.repositories.user_repository import UserRepository
from app.schemas.user import UserResponse, UserUpdate
from app.core.config import settings
from app.core.exceptions import NotFoundException


class UserService:
    def __init__(self, db: Session):
        self.user_repo = UserRepository(db)

    def get_by_id(self, user_id: uuid.UUID) -> UserResponse:
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundException("Utilisateur")
        return UserResponse.model_validate(user)

    def update_profile(self, user_id: uuid.UUID, data: UserUpdate) -> UserResponse:
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundException("Utilisateur")
        user = self.user_repo.update(user, data)
        return UserResponse.model_validate(user)

    def upload_profile_picture(self, user_id: uuid.UUID, file: UploadFile) -> UserResponse:
        """Sauvegarde la photo de profil et met à jour l'URL."""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundException("Utilisateur")

        upload_dir = Path(settings.UPLOAD_DIR) / "profile_pictures"
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Extension sécurisée
        ext = Path(file.filename).suffix.lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Seuls les formats JPG, PNG et WEBP sont acceptés.",
            )

        filename = f"{user_id}{ext}"
        file_path = upload_dir / filename

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        url = f"/uploads/profile_pictures/{filename}"
        user = self.user_repo.update_profile_picture(user, url)
        return UserResponse.model_validate(user)

    def delete_account(self, user_id: uuid.UUID) -> None:
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundException("Utilisateur")
        self.user_repo.delete(user)
