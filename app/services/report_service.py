"""
app/services/report_service.py
Génération du rapport PDF via ReportLab.
Inclut désormais les commentaires de tâche sous chaque ligne du tableau.
"""

import uuid
import io
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from sqlalchemy.orm import Session, joinedload

from app.repositories.user_repository import UserRepository
from app.repositories.task_repository import TaskRepository
from app.models.task import Task, TaskStatus
from app.models.task_comment import TaskComment
from app.core.exceptions import NotFoundException

# ── Palette SABC ───────────────────────────────────────────────────────────────
SABC_RED   = colors.HexColor("#C0392B")
SABC_DARK  = colors.HexColor("#1A1A2E")
SABC_GREY  = colors.HexColor("#7F8C8D")
SABC_LIGHT = colors.HexColor("#F2F3F4")
WHITE      = colors.white


# ── Utilitaire : HTML → texte brut ────────────────────────────────────────────

class _HTMLStripper(HTMLParser):
    """Extrait le texte brut d'un fragment HTML sans dépendance externe."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def handle_starttag(self, tag: str, attrs) -> None:
        # Insérer un saut de ligne après les balises de bloc
        if tag in ("p", "br", "li", "div", "h1", "h2", "h3", "h4", "tr"):
            self._parts.append("\n")

    @property
    def text(self) -> str:
        return " ".join("".join(self._parts).split())


def _html_to_plain(html: str) -> str:
    """Convertit du HTML en texte lisible, sans dépendance externe (bs4 non requis)."""
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.text.strip()


class ReportService:
    def __init__(self, db: Session):
        self.db        = db
        self.user_repo = UserRepository(db)
        self.task_repo = TaskRepository(db)

    def generate_pdf(
        self,
        user_id: uuid.UUID,
        date_from: Optional[date] = None,
        date_to:   Optional[date] = None,
    ) -> bytes:
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundException("Utilisateur")

        # Chargement des tâches avec leurs commentaires en une seule requête
        tasks = (
            self.db.query(Task)
            .options(joinedload(Task.comments))
            .filter(
                Task.user_id == user_id,
                Task.task_date >= (date_from or user.internship_start_date),
                Task.task_date <= (date_to   or date.today()),
            )
            .order_by(Task.task_date.asc(), Task.start_time.asc())
            .limit(10_000)
            .all()
        )

        stats  = self.task_repo.get_stats(user_id)
        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=2 * cm, rightMargin=2 * cm,
            topMargin=2 * cm,  bottomMargin=2 * cm,
            title=f"Rapport WakAgenda – {user.full_name}",
            author="WakAgenda – Boissons du Cameroun",
        )

        styles = self._build_styles()
        story: list = []

        story += self._cover_page(user, styles, date_from, date_to)
        story.append(PageBreak())
        story += self._stats_section(stats, styles)
        story.append(Spacer(1, 0.5 * cm))
        story += self._tasks_section(tasks, styles)

        story.append(Spacer(1, 1 * cm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=SABC_GREY))
        story.append(Spacer(1, 0.3 * cm))
        story.append(
            Paragraph(
                f"Rapport généré le {datetime.now(timezone.utc).strftime('%d/%m/%Y à %H:%M')} UTC"
                f" | WakAgenda v1.0 – Boissons du Cameroun",
                styles["footer"],
            )
        )

        doc.build(story)
        return buffer.getvalue()

    # ── Styles ─────────────────────────────────────────────────────────────────

    def _build_styles(self) -> dict:
        return {
            "title":        ParagraphStyle("title",        fontSize=28, textColor=SABC_RED,  alignment=TA_CENTER, spaceAfter=6,   fontName="Helvetica-Bold"),
            "subtitle":     ParagraphStyle("subtitle",     fontSize=14, textColor=SABC_DARK, alignment=TA_CENTER, spaceAfter=4,   fontName="Helvetica"),
            "label":        ParagraphStyle("label",        fontSize=10, textColor=SABC_GREY, alignment=TA_CENTER, spaceAfter=2,   fontName="Helvetica"),
            "h2":           ParagraphStyle("h2",           fontSize=14, textColor=SABC_RED,  alignment=TA_LEFT,   spaceBefore=12, spaceAfter=6,  fontName="Helvetica-Bold"),
            "comment_head": ParagraphStyle("comment_head", fontSize=9,  textColor=WHITE,     alignment=TA_LEFT,   spaceAfter=3,   fontName="Helvetica-Bold",
                                           backColor=SABC_RED, leftIndent=6, rightIndent=6, spaceBefore=4),
            "comment_body": ParagraphStyle("comment_body", fontSize=8,  textColor=SABC_DARK, alignment=TA_LEFT,   spaceAfter=4,   fontName="Helvetica",
                                           leftIndent=6, rightIndent=6, leading=12),
            "body":         ParagraphStyle("body",         fontSize=9,  textColor=SABC_DARK, alignment=TA_LEFT,   spaceAfter=4,   fontName="Helvetica"),
            "footer":       ParagraphStyle("footer",       fontSize=7,  textColor=SABC_GREY, alignment=TA_CENTER, fontName="Helvetica-Oblique"),
            "cell":         ParagraphStyle("cell",         fontSize=8,  textColor=SABC_DARK, fontName="Helvetica"),
            "cell_head":    ParagraphStyle("cell_head",    fontSize=8,  textColor=WHITE,      fontName="Helvetica-Bold"),
        }

    # ── Page de garde ──────────────────────────────────────────────────────────

    def _cover_page(self, user, styles, date_from, date_to) -> list:
        elements = [Spacer(1, 3 * cm)]
        elements.append(Paragraph("WakAgenda", styles["title"]))
        elements.append(Paragraph("Rapport d'activité du stagiaire", styles["subtitle"]))
        elements.append(Spacer(1, 0.5 * cm))
        elements.append(HRFlowable(width="60%", thickness=2, color=SABC_RED, hAlign="CENTER"))
        elements.append(Spacer(1, 1.5 * cm))

        info_data = [
            ["Stagiaire",          user.full_name],
            ["Département",        user.department],
            ["Encadrant",          user.supervisor_name],
            ["Début de stage",     user.internship_start_date.strftime("%d/%m/%Y")],
            ["Période du rapport",
             f"{(date_from or user.internship_start_date).strftime('%d/%m/%Y')} → "
             f"{(date_to or date.today()).strftime('%d/%m/%Y')}"],
        ]
        tbl = Table(info_data, colWidths=[5 * cm, 10 * cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (0, -1), SABC_LIGHT),
            ("TEXTCOLOR",      (0, 0), (0, -1), SABC_RED),
            ("FONTNAME",       (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE",       (0, 0), (-1, -1), 10),
            ("PADDING",        (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [SABC_LIGHT, WHITE]),
            ("GRID",           (0, 0), (-1, -1), 0.5, SABC_GREY),
            ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(tbl)
        elements.append(Spacer(1, 2 * cm))
        elements.append(Paragraph("Boissons du Cameroun – DSI", styles["label"]))
        elements.append(Paragraph("Département Transformation Digitale, Organisation et Projets", styles["label"]))
        elements.append(Paragraph("77, rue Prince Bell – Bali, Douala", styles["label"]))
        return elements

    # ── Statistiques ───────────────────────────────────────────────────────────

    def _stats_section(self, stats, styles) -> list:
        elements = [Paragraph("Statistiques récapitulatives", styles["h2"])]

        summary_data = [
            [Paragraph("Total tâches", styles["cell_head"]),
             Paragraph("Terminées",    styles["cell_head"]),
             Paragraph("En retard",    styles["cell_head"]),
             Paragraph("Aujourd'hui", styles["cell_head"])],
            [Paragraph(str(stats.total),     styles["cell"]),
             Paragraph(str(stats.completed), styles["cell"]),
             Paragraph(str(stats.overdue),   styles["cell"]),
             Paragraph(str(stats.today),     styles["cell"])],
        ]
        tbl = Table(summary_data, colWidths=[4 * cm] * 4)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), SABC_RED),
            ("BACKGROUND", (0, 1), (-1, 1), SABC_LIGHT),
            ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
            ("FONTSIZE",   (1, 1), (-1, -1), 16),
            ("FONTNAME",   (1, 1), (-1, -1), "Helvetica-Bold"),
            ("GRID",       (0, 0), (-1, -1), 0.5, SABC_GREY),
            ("PADDING",    (0, 0), (-1, -1), 10),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(tbl)
        elements.append(Spacer(1, 0.5 * cm))

        elements.append(Paragraph("Répartition par catégorie", styles["h2"]))
        cat_data = [
            [Paragraph(k, styles["cell"]), Paragraph(str(v), styles["cell"])]
            for k, v in stats.by_category.items()
        ]
        if cat_data:
            cat_data.insert(0, [
                Paragraph("Catégorie", styles["cell_head"]),
                Paragraph("Nombre",    styles["cell_head"]),
            ])
            tbl2 = Table(cat_data, colWidths=[8 * cm, 4 * cm])
            tbl2.setStyle(TableStyle([
                ("BACKGROUND",     (0, 0), (-1, 0), SABC_RED),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, SABC_LIGHT]),
                ("GRID",           (0, 0), (-1, -1), 0.5, SABC_GREY),
                ("PADDING",        (0, 0), (-1, -1), 6),
                ("ALIGN",          (1, 0), (1, -1), "CENTER"),
            ]))
            elements.append(tbl2)
        return elements

    # ── Liste des tâches + commentaires ───────────────────────────────────────

    def _tasks_section(self, tasks: list[Task], styles: dict) -> list:
        elements: list = [
            Spacer(1, 0.5 * cm),
            Paragraph("Liste chronologique des tâches", styles["h2"]),
        ]

        if not tasks:
            elements.append(Paragraph("Aucune tâche enregistrée pour cette période.", styles["body"]))
            return elements

        headers = ["Date", "Intitulé", "Catégorie", "Domaine", "Statut", "Durée"]
        col_widths = [2.5 * cm, 6 * cm, 3 * cm, 3 * cm, 2.5 * cm, 2 * cm]

        # ── En-tête du tableau (répété sur chaque page via repeatRows) ─────────
        header_row = [Paragraph(h, styles["cell_head"]) for h in headers]

        for i, task in enumerate(tasks):
            # Calcul durée
            duration_min = (
                datetime.combine(task.task_date, task.end_time) -
                datetime.combine(task.task_date, task.start_time)
            ).seconds // 60
            duration_str = f"{duration_min // 60}h{duration_min % 60:02d}"

            # Couleur de fond selon statut
            if task.status == TaskStatus.DONE:
                row_bg = colors.HexColor("#D5F5E3")
            elif task.status == TaskStatus.CANCELLED:
                row_bg = colors.HexColor("#FADBD8")
            elif i % 2 == 0:
                row_bg = SABC_LIGHT
            else:
                row_bg = WHITE

            data_row = [
                Paragraph(task.task_date.strftime("%d/%m/%Y"), styles["cell"]),
                Paragraph(task.title[:45] + ("…" if len(task.title) > 45 else ""), styles["cell"]),
                Paragraph(task.category.value,  styles["cell"]),
                Paragraph(task.effective_domain_name, styles["cell"]),
                Paragraph(task.status.value,    styles["cell"]),
                Paragraph(duration_str,          styles["cell"]),
            ]

            row_tbl = Table(
                [header_row, data_row],
                colWidths=col_widths,
                repeatRows=1,
            )
            row_tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), SABC_RED),
                ("BACKGROUND", (0, 1), (-1, 1), row_bg),
                ("GRID",       (0, 0), (-1, -1), 0.3, SABC_GREY),
                ("PADDING",    (0, 0), (-1, -1), 5),
                ("FONTSIZE",   (0, 0), (-1, -1), 8),
                ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ]))

            # Bloc tâche + éventuel commentaire, non sécable entre les deux
            block: list = [row_tbl]

            comment: TaskComment | None = (
                task.comments[0] if task.comments else None
            )
            if comment:
                plain_text = _html_to_plain(comment.content)
                block.append(
                    Paragraph(
                        f"Commentaire — {task.title[:40]}{'…' if len(task.title) > 40 else ''}",
                        styles["comment_head"],
                    )
                )
                block.append(Paragraph(plain_text, styles["comment_body"]))
                block.append(
                    HRFlowable(width="100%", thickness=0.4, color=SABC_GREY, spaceAfter=4)
                )

            elements.append(KeepTogether(block))
            elements.append(Spacer(1, 0.3 * cm))

        return elements