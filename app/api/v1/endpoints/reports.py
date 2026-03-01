"""
app/api/v1/endpoints/reports.py
Route de génération du rapport PDF (BF-19 à BF-21).
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Rapports PDF"])


@router.get(
    "/pdf",
    summary="Générer et télécharger le rapport PDF",
    response_class=Response,
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "Rapport PDF généré",
        }
    },
)
def generate_pdf_report(
    date_from: Optional[date] = Query(None, description="Date de début (YYYY-MM-DD). Défaut : début du stage."),
    date_to:   Optional[date] = Query(None, description="Date de fin (YYYY-MM-DD). Défaut : aujourd'hui."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Génère un rapport PDF complet de l'activité du stagiaire.
    - Page de garde avec informations personnelles
    - Statistiques récapitulatives
    - Liste chronologique de toutes les tâches
    Correspond à BF-19, BF-20, BF-21.
    """
    pdf_bytes = ReportService(db).generate_pdf(
        user_id=current_user.id,
        date_from=date_from,
        date_to=date_to,
    )

    filename = f"rapport_wakagenda_{current_user.last_name.lower()}_{date.today().isoformat()}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
