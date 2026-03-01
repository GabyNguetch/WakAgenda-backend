"""
app/core/security.py
Gestion JWT et hachage bcrypt.
Principe SOLID : Single Responsibility – sécurité uniquement.

Fix : passlib est incompatible avec bcrypt >= 4.x (AttributeError: __about__).
      On utilise bcrypt directement via un wrapper qui respecte la même interface.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


# ── Mots de passe ──────────────────────────────────────────────────────────────

def hash_password(plain_password: str) -> str:
    """Hache un mot de passe en clair via bcrypt (sans passlib)."""
    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie un mot de passe contre son hash bcrypt (sans passlib)."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


# ── Tokens JWT ─────────────────────────────────────────────────────────────────

def create_access_token(subject: Any, expires_delta: Optional[timedelta] = None) -> str:
    """
    Génère un JWT signé.
    :param subject: Identifiant de l'utilisateur (user_id sous forme de str)
    :param expires_delta: Durée de vie du token (optionnel)
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    """
    Décode un JWT et retourne le subject (user_id).
    Retourne None si le token est invalide ou expiré.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        subject: str = payload.get("sub")
        return subject
    except JWTError:
        return None