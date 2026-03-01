"""
app/api/v1/endpoints/users.py
Routes : profil utilisateur courant + upload photo.
"""

import uuid
from fastapi import APIRouter, Depends, UploadFile, File, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Utilisateurs"])


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Profil de l'utilisateur connecté",
)
def get_me(current_user: User = Depends(get_current_user)):
    """Retourne le profil complet de l'utilisateur authentifié (BF-05)."""
    return UserResponse.model_validate(current_user)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Récupérer un utilisateur par son ID",
)
def get_user_by_id(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourne le profil d'un utilisateur par son UUID."""
    return UserService(db).get_by_id(user_id)


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Mettre à jour le profil",
)
def update_profile(
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Modification partielle du profil (BF-05)."""
    return UserService(db).update_profile(current_user.id, data)


@router.post(
    "/me/picture",
    response_model=UserResponse,
    summary="Uploader une photo de profil",
)
def upload_picture(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload de la photo de profil (BF-02 – champ optionnel)."""
    return UserService(db).upload_profile_picture(current_user.id, file)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer son compte",
)
def delete_account(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Suppression du compte et de toutes les données associées."""
    UserService(db).delete_account(current_user.id)
