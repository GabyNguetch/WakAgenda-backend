"""
app/api/deps.py
Dépendances FastAPI partagées.
Fournit l'utilisateur courant à partir du token JWT.

Fix : remplacement de OAuth2PasswordBearer par HTTPBearer.
      Le Swagger affiche maintenant une simple boîte "Value" où
      on colle directement le Bearer token — sans formulaire username/password.
"""

import uuid
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import decode_access_token
from app.core.exceptions import CredentialsException
from app.models.user import User

http_bearer = HTTPBearer(auto_error=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
    db: Session = Depends(get_db),
) -> User:
    """
    Dépendance qui extrait et valide le JWT depuis le header Authorization: Bearer <token>,
    puis charge l'utilisateur depuis la base de données.
    """
    token = credentials.credentials

    user_id_str = decode_access_token(token)
    if not user_id_str:
        raise CredentialsException()

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise CredentialsException()

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise CredentialsException("Utilisateur introuvable ou désactivé.")

    return user