"""
app/db/base_class.py
Classe DeclarativeBase partagée (sans imports circulaires).
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
