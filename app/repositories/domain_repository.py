"""
app/repositories/domain_repository.py
Couche d'accès aux données pour les domaines métier.
"""

import uuid
import re
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.domain import Domain


def _slugify(name: str) -> str:
    """Convertit un nom lisible en slug URL-safe."""
    slug = name.lower().strip()
    slug = re.sub(r"[àáâãäå]", "a", slug)
    slug = re.sub(r"[èéêë]", "e", slug)
    slug = re.sub(r"[ìíîï]", "i", slug)
    slug = re.sub(r"[òóôõö]", "o", slug)
    slug = re.sub(r"[ùúûü]", "u", slug)
    slug = re.sub(r"[ç]", "c", slug)
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


class DomainRepository:
    """Toutes les opérations DB relatives aux domaines."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, domain_id: uuid.UUID) -> Optional[Domain]:
        return self.db.get(Domain, domain_id)

    def get_by_slug(self, slug: str) -> Optional[Domain]:
        return self.db.query(Domain).filter(Domain.slug == slug).first()

    def get_by_name(self, name: str) -> Optional[Domain]:
        return (
            self.db.query(Domain)
            .filter(Domain.name.ilike(name))
            .first()
        )

    def get_all(self) -> List[Domain]:
        return self.db.query(Domain).order_by(Domain.is_system.desc(), Domain.name.asc()).all()

    def name_exists(self, name: str) -> bool:
        return self.db.query(Domain.id).filter(Domain.name.ilike(name)).first() is not None

    def create(self, name: str, description: Optional[str] = None, is_system: bool = False) -> Domain:
        domain = Domain(
            name=name.strip(),
            slug=_slugify(name),
            description=description,
            is_system=is_system,
        )
        self.db.add(domain)
        self.db.commit()
        self.db.refresh(domain)
        return domain

    def delete(self, domain: Domain) -> None:
        self.db.delete(domain)
        self.db.commit()