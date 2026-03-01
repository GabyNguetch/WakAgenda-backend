"""
app/db/base.py
Classe de base SQLAlchemy partagée par tous les modèles.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import explicite de tous les modèles pour qu'Alembic les détecte
from app.models.user import User          # noqa: F401, E402
from app.models.task import Task          # noqa: F401, E402
from app.models.notification import Notification  # noqa: F401, E402
