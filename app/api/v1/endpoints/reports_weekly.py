"""
app/api/v1/endpoints/reports_weekly.py
Route : GET /api/v1/reports/weekly-schedule
Génère un emploi du temps hebdomadaire en PDF orientation paysage.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable
)
import io

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.task import Task, TaskStatus, EventCategory
from app.repositories.task_repository import TaskRepository

router = APIRouter(prefix="/reports", tags=["Rapports PDF"])

# ── Palette SABC ───────────────────────────────────────────────────────────────
SABC_RED    = colors.HexColor("#C8102E")
SABC_ORANGE = colors.HexColor("#E8600A")
SABC_DARK   = colors.HexColor("#1A1A2E")
SABC_GREY   = colors.HexColor("#7F8C8D")
SABC_LIGHT  = colors.HexColor("#F2F3F4")
WHITE       = colors.white

# Couleurs de statut
STATUS_COLORS = {
    "Terminé":     colors.HexColor("#D5F5E3"),
    "Annulé":      colors.HexColor("#FADBD8"),
    "En retard":   colors.HexColor("#FDEBD0"),
    "Manquée":     colors.HexColor("#F9EBEA"),
    "En cours":    colors.HexColor("#D6EAF8"),
    "À faire":     SABC_LIGHT,
}

DAYS_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def _monday_of_week(ref: date) -> date:
    """Retourne le lundi de la semaine contenant ref."""
    return ref - timedelta(days=ref.weekday())


def _format_week_label(monday: date) -> str:
    MONTHS_FR = [
        "", "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre"
    ]
    sunday = monday + timedelta(days=6)
    if monday.month == sunday.month:
        return (
            f"Semaine du {monday.day} au {sunday.day} "
            f"{MONTHS_FR[monday.month]} {monday.year}"
        )
    return (
        f"Semaine du {monday.day} {MONTHS_FR[monday.month]} "
        f"au {sunday.day} {MONTHS_FR[sunday.month]} {sunday.year}"
    )


def _category_color(category_value: str) -> colors.Color:
    mapping = {
        "Réunion":        colors.HexColor("#AED6F1"),
        "Développement":  colors.HexColor("#A9DFBF"),
        "Formation":      colors.HexColor("#F9E79F"),
        "Rendu":          colors.HexColor("#F5CBA7"),
        "Autre":          colors.HexColor("#D7BDE2"),
    }
    return mapping.get(category_value, SABC_LIGHT)


def _generate_weekly_pdf(user: User, tasks: list, monday: date) -> bytes:
    PAGE_W, PAGE_H = landscape(A4)
    MARGIN = 1.5 * cm
    TEXT_W = PAGE_W - 2 * MARGIN

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=1.8 * cm,
        title=f"Emploi du temps — {user.full_name}",
    )

    # ── Styles ────────────────────────────────────────────────────────────────
    title_style = ParagraphStyle(
        "title", fontName="Helvetica-Bold", fontSize=14,
        textColor=SABC_DARK, alignment=TA_CENTER, spaceAfter=4,
    )
    sub_style = ParagraphStyle(
        "sub", fontName="Helvetica", fontSize=9,
        textColor=SABC_GREY, alignment=TA_CENTER, spaceAfter=2,
    )
    day_head_style = ParagraphStyle(
        "day_head", fontName="Helvetica-Bold", fontSize=9,
        textColor=WHITE, alignment=TA_CENTER,
    )
    task_title_style = ParagraphStyle(
        "task_title", fontName="Helvetica-Bold", fontSize=7,
        textColor=SABC_DARK, alignment=TA_LEFT, leading=9,
    )
    task_meta_style = ParagraphStyle(
        "task_meta", fontName="Helvetica", fontSize=6,
        textColor=SABC_GREY, alignment=TA_LEFT, leading=8,
    )
    task_cat_style = ParagraphStyle(
        "task_cat", fontName="Helvetica-Oblique", fontSize=6,
        textColor=SABC_DARK, alignment=TA_LEFT, leading=8,
    )
    empty_style = ParagraphStyle(
        "empty", fontName="Helvetica-Oblique", fontSize=7,
        textColor=SABC_GREY, alignment=TA_CENTER,
    )
    footer_style = ParagraphStyle(
        "footer", fontName="Helvetica-Oblique", fontSize=7,
        textColor=SABC_GREY, alignment=TA_CENTER,
    )

    story = []

    # ── En-tête ───────────────────────────────────────────────────────────────
    story.append(Paragraph(
        f"Emploi du temps — {user.full_name}",
        title_style,
    ))
    story.append(Paragraph(_format_week_label(monday), sub_style))
    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=SABC_RED))
    story.append(Spacer(1, 0.3 * cm))

    # ── Organisation des tâches par jour ──────────────────────────────────────
    days_tasks: dict[int, list[Task]] = {i: [] for i in range(7)}
    for task in tasks:
        day_idx = (task.task_date - monday).days
        if 0 <= day_idx <= 6:
            days_tasks[day_idx].append(task)

    # Trier par heure de début
    for i in range(7):
        days_tasks[i].sort(key=lambda t: t.start_time)

    # ── En-tête du tableau ────────────────────────────────────────────────────
    col_w = TEXT_W / 7
    header_row = []
    for i in range(7):
        day_date = monday + timedelta(days=i)
        header_row.append(Paragraph(
            f"{DAYS_FR[i]}<br/>{day_date.strftime('%d/%m')}",
            day_head_style,
        ))

    # ── Contenu des cellules ──────────────────────────────────────────────────
    def _task_cell(task: Task) -> list:
        """Construit le contenu d'une cellule de tâche."""
        cell_bg = STATUS_COLORS.get(task.status.value if hasattr(task.status, 'value') else task.status, SABC_LIGHT)
        items = [
            Paragraph(
                task.title[:35] + ("…" if len(task.title) > 35 else ""),
                task_title_style,
            ),
            Paragraph(
                f"{task.start_time.strftime('%H:%M')} – {task.end_time.strftime('%H:%M')}",
                task_meta_style,
            ),
            Paragraph(
                task.category.value if hasattr(task.category, 'value') else str(task.category),
                task_cat_style,
            ),
        ]
        return items

    # Construire les lignes : une seule ligne de données (cellules avec stacks)
    max_tasks = max((len(v) for v in days_tasks.values()), default=0)

    if max_tasks == 0:
        data_row = [Paragraph("Aucune tâche", empty_style) for _ in range(7)]
        table_data = [header_row, data_row]
        col_heights = [1.0 * cm, 1.2 * cm]
    else:
        # Créer une ligne par tâche (max_tasks lignes)
        table_data = [header_row]
        col_heights = [1.0 * cm]

        for row_idx in range(max_tasks):
            row = []
            for col_idx in range(7):
                day_task_list = days_tasks[col_idx]
                if row_idx < len(day_task_list):
                    task = day_task_list[row_idx]
                    cell_content = _task_cell(task)
                    # Empiler les paragraphes
                    from reportlab.platypus import KeepTogether
                    row.append(cell_content)
                else:
                    row.append("")
            table_data.append(row)
            col_heights.append(1.8 * cm)

    tbl = Table(
        table_data,
        colWidths=[col_w] * 7,
        rowHeights=col_heights,
    )

    # Style de base
    style_cmds = [
        # En-tête
        ("BACKGROUND",   (0, 0), (-1, 0), SABC_RED),
        ("TEXTCOLOR",    (0, 0), (-1, 0), WHITE),
        ("ALIGN",        (0, 0), (-1, 0), "CENTER"),
        ("VALIGN",       (0, 0), (-1, 0), "MIDDLE"),
        # Corps
        ("VALIGN",       (0, 1), (-1, -1), "TOP"),
        ("GRID",         (0, 0), (-1, -1), 0.4, SABC_GREY),
        ("PADDING",      (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, SABC_LIGHT]),
    ]

    # Colorier les cellules de tâche selon le statut
    if max_tasks > 0:
        for row_idx in range(max_tasks):
            for col_idx in range(7):
                task_list = days_tasks[col_idx]
                if row_idx < len(task_list):
                    task = task_list[row_idx]
                    bg = STATUS_COLORS.get(
                        task.status.value if hasattr(task.status, 'value') else str(task.status),
                        SABC_LIGHT,
                    )
                    style_cmds.append(
                        ("BACKGROUND", (col_idx, row_idx + 1), (col_idx, row_idx + 1), bg)
                    )

    tbl.setStyle(TableStyle(style_cmds))
    story.append(tbl)

    # ── Pied de page ──────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.4 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=SABC_GREY))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        f"Généré le {datetime.now(timezone.utc).strftime('%d/%m/%Y à %H:%M')} UTC"
        f"  |  WakAgenda v1.0 — Boissons du Cameroun",
        footer_style,
    ))

    doc.build(story)
    return buffer.getvalue()


@router.get(
    "/weekly-schedule",
    summary="Emploi du temps hebdomadaire en PDF (paysage)",
    response_class=Response,
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "Emploi du temps PDF généré",
        }
    },
)
def generate_weekly_schedule(
    week_start: Optional[date] = Query(
        None,
        description="Lundi de la semaine souhaitée (YYYY-MM-DD). Défaut : semaine courante.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Génère un emploi du temps hebdomadaire en PDF orientation paysage.
    - Tableau à 7 colonnes (lundi → dimanche)
    - Tâches organisées chronologiquement dans chaque colonne
    - Couleurs par statut
    """
    monday = _monday_of_week(week_start or date.today())
    sunday = monday + timedelta(days=6)

    task_repo = TaskRepository(db)
    tasks = task_repo.get_all_for_user(
        user_id=current_user.id,
        date_from=monday,
        date_to=sunday,
        limit=500,
    )

    pdf_bytes = _generate_weekly_pdf(current_user, tasks, monday)

    filename = f"emploi_du_temps_semaine_{monday.isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )