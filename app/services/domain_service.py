"""
app/services/domain_service.py
Logique métier pour les domaines métier personnalisés.
"""

import uuid
from typing import List

from sqlalchemy.orm import Session

from app.repositories.domain_repository import DomainRepository
from app.schemas.domain import DomainCreate, DomainResponse
from app.core.exceptions import NotFoundException, AlreadyExistsException, ForbiddenException


class DomainService:
    def __init__(self, db: Session):
        self.domain_repo = DomainRepository(db)

    def list_domains(self) -> List[DomainResponse]:
        domains = self.domain_repo.get_all()
        return [DomainResponse.model_validate(d) for d in domains]

    def create_domain(self, data: DomainCreate) -> DomainResponse:
        if self.domain_repo.name_exists(data.name):
            raise AlreadyExistsException(f"Le domaine « {data.name} »")
        domain = self.domain_repo.create(
            name=data.name,
            description=data.description,
            is_system=False,
        )
        return DomainResponse.model_validate(domain)

    def get_domain(self, domain_id: uuid.UUID) -> DomainResponse:
        domain = self.domain_repo.get_by_id(domain_id)
        if not domain:
            raise NotFoundException("Domaine")
        return DomainResponse.model_validate(domain)

    def delete_domain(self, domain_id: uuid.UUID) -> None:
        domain = self.domain_repo.get_by_id(domain_id)
        if not domain:
            raise NotFoundException("Domaine")
        if domain.is_system:
            raise ForbiddenException("Les domaines système ne peuvent pas être supprimés.")
        self.domain_repo.delete(domain)