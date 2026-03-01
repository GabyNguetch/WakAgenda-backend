"""
app/api/v1/endpoints/auth.py
Routes : POST /register (onboarding) et POST /login.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.user import UserCreate
from app.schemas.auth import LoginRequest, TokenResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentification"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Onboarding – Créer un compte stagiaire",
)
def register(data: UserCreate, db: Session = Depends(get_db)):
    """
    Première connexion : crée le profil du stagiaire et retourne un JWT.
    Correspond à BF-01 et BF-02.
    """
    return AuthService(db).register(data)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Connexion – Obtenir un token JWT",
)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """
    Connexions récurrentes : vérifie email + mot de passe et retourne un JWT.
    Correspond à BF-03.
    """
    return AuthService(db).login(data.email, data.password)
