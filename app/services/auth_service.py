"""
app/services/auth_service.py
Logique métier pour l'authentification.
Principe SOLID : Single Responsibility + Dependency Inversion.
"""

from sqlalchemy.orm import Session

from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate
from app.schemas.auth import TokenResponse
from app.core.security import verify_password, create_access_token
from app.core.exceptions import CredentialsException, AlreadyExistsException
from app.schemas.user import UserResponse


class AuthService:
    def __init__(self, db: Session):
        self.user_repo = UserRepository(db)

    def register(self, data: UserCreate) -> TokenResponse:
        """Crée un compte et retourne un token (onboarding)."""
        if self.user_repo.email_exists(data.email):
            raise AlreadyExistsException("Un compte avec cet email")

        user = self.user_repo.create(data)
        token = create_access_token(subject=user.id)

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
        )

    def login(self, email: str, password: str) -> TokenResponse:
        """Vérifie les credentials et retourne un token JWT."""
        user = self.user_repo.get_by_email(email)

        if not user or not verify_password(password, user.hashed_password):
            raise CredentialsException("Email ou mot de passe incorrect.")

        if not user.is_active:
            raise CredentialsException("Ce compte est désactivé.")

        token = create_access_token(subject=user.id)

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
        )
