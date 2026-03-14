"""
app/core/config.py  ← FICHIER MODIFIÉ
Configuration centralisée via pydantic-settings.

AJOUTS PAR RAPPORT À LA VERSION ORIGINALE :
  - SMTP_FROM     : adresse expéditeur pour le broadcast
  (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_USE_TLS
   existaient déjà dans email_service.py — ajoutés ici pour cohérence)
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    APP_NAME: str = "WakAgenda"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # URL de base (utilisée dans les liens email du scheduler)
    APP_BASE_URL: str = "http://localhost:8000"

    # Base de données
    DATABASE_URL: str = "postgresql://wakagenda_user:wakagenda_pass@localhost:5432/wakagenda_db"

    # Sécurité JWT
    SECRET_KEY: str = "changez-moi-en-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24h

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # Upload
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 5

    # SMTP — utilisé par email_service.py ET broadcast.py
    SMTP_HOST:     str  = ""
    SMTP_PORT:     int  = 587
    SMTP_USER:     str  = ""
    SMTP_PASSWORD: str  = ""
    SMTP_USE_TLS:  bool = False
    SMTP_FROM:     str  = ""   # ← NEW  adresse expéditeur pour le broadcast

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]


settings = Settings()