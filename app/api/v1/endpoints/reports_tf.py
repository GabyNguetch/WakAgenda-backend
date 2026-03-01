"""
app/api/v1/endpoints/reports_tf.py

Route de génération du rapport technico-fonctionnel PDF.
"""

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.report_technico_fonctionnel import RapportTechnicoFonctionnelService

router = APIRouter(prefix="/reports", tags=["Rapports PDF"])


@router.get(
    "/technico-fonctionnel",
    summary="Générer le rapport technico-fonctionnel PDF",
    response_class=Response,
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "Rapport technico-fonctionnel PDF généré",
        }
    },
)
def generate_rapport_tf(
    date_from: Optional[date] = Query(None, description="Date de début (YYYY-MM-DD)."),
    date_to:   Optional[date] = Query(None, description="Date de fin (YYYY-MM-DD)."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Génère le rapport technico-fonctionnel structuré :
    - Page de garde (style mémoire ENSPY/SABC)
    - Table des matières
    - Chapitres par domaine, sections par tâche, contenu = commentaires
    - Images insérées si disponibles
    - Pied de page WakAgenda + dernière page avec logo
    """
    pdf_bytes = RapportTechnicoFonctionnelService(db).generate_pdf(
        user_id=current_user.id,
        date_from=date_from,
        date_to=date_to,
    )

    filename = (
        f"rapport_tf_wakagenda_{current_user.last_name.lower()}"
        f"_{date.today().isoformat()}.pdf"
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )