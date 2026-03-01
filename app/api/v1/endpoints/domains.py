"""
app/api/v1/endpoints/domains.py
Routes CRUD pour les domaines métier auto-incrémentables.
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.domain import DomainCreate, DomainResponse
from app.services.domain_service import DomainService

router = APIRouter(prefix="/domains", tags=["Domaines"])


@router.get(
    "",
    response_model=List[DomainResponse],
    summary="Lister tous les domaines (système + personnalisés)",
)
def list_domains(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return DomainService(db).list_domains()


@router.post(
    "",
    response_model=DomainResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un nouveau domaine personnalisé",
)
def create_domain(
    data: DomainCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Crée un domaine personnalisé et l'ajoute à la liste commune."""
    return DomainService(db).create_domain(data)


@router.get(
    "/{domain_id}",
    response_model=DomainResponse,
    summary="Détails d'un domaine",
)
def get_domain(
    domain_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return DomainService(db).get_domain(domain_id)


@router.delete(
    "/{domain_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un domaine personnalisé",
)
def delete_domain(
    domain_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    DomainService(db).delete_domain(domain_id)