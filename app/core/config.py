"""
app/core/config.py
Configuration centralisée via pydantic-settings.
Principe SOLID : Single Responsibility – ce module gère uniquement la config.
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

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]


settings = Settings()
