"""
app/core/config.py
Configuration centralisée via pydantic-settings.
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
    APP_NAME:     str  = "WakAgenda"
    APP_VERSION:  str  = "1.0.0"
    DEBUG:        bool = False
    APP_BASE_URL: str  = "http://localhost:8000"

    # Base de données
    DATABASE_URL: str = "postgresql://wakagenda_user:wakagenda_pass@localhost:5432/wakagenda_db"

    # Sécurité JWT
    SECRET_KEY:                  str = "changez-moi-en-production"
    ALGORITHM:                   str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24h

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000, https://wakagenda-admin.vercel.app/, https://wak-agenda.vercel.app/"

    # Upload
    UPLOAD_DIR:         str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 5

    # ── SMTP Gmail ─────────────────────────────────────────────────────────────
    # Variables à définir dans .env ou sur Render :
    #   SMTP_HOST     = smtp.gmail.com
    #   SMTP_PORT     = 465
    #   SMTP_USER     = wakagenda@gmail.com
    #   SMTP_PASSWORD = xxxx xxxx xxxx xxxx   (App Password Gmail, PAS le vrai mdp)
    #   SMTP_FROM     = WakAgenda <wakagenda@gmail.com>
    #   SMTP_USE_TLS  = true
    SMTP_HOST:     str  = ""
    SMTP_PORT:     int  = 465
    SMTP_USER:     str  = ""
    SMTP_PASSWORD: str  = ""
    SMTP_FROM:     str  = ""
    SMTP_USE_TLS:  bool = True   # True = SMTP_SSL port 465 (Gmail recommandé)

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]


settings = Settings()