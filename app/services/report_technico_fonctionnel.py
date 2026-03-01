"""
app/services/report_technico_fonctionnel.py

Génération du rapport technico-fonctionnel PDF – WakAgenda.
Structure inspirée du mémoire de fin d'études ENSPY / SABC.

Structure :
  - Page de garde (bordure double rouge SABC avec coins décorés, logos grands, colonnes ENSPY/SABC)
  - Table des matières (générée automatiquement)
  - Corps : domaines = chapitres, intitulés des tâches = sections
  - Commentaires rendus avec mise en forme riche (bold, italic, listes, titres, images base64)
  - Images inline extraites du HTML TipTap + images fichier par task_id
  - Pied de page "WakAgenda" sur chaque page (sauf couverture)
  - Dernière page avec logo WakAgenda très grand et centré

Logos attendus dans : app/assets/report/
  - logo.png        → logo WakAgenda / ENSPY (gauche couverture + dernière page)
  - logo_sabc.png   → logo SABC (droite couverture)
"""

import base64
import io
import re
import uuid
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional, List, Tuple

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    HRFlowable,
    PageBreak,
    KeepTogether,
    Image,
    NextPageTemplate,
    ListFlowable,
    ListItem,
)
from reportlab.platypus import ActionFlowable
from reportlab.lib import colors
from sqlalchemy.orm import Session, joinedload

from app.repositories.user_repository import UserRepository
from app.repositories.task_repository import TaskRepository
from app.models.task import Task, TaskStatus
from app.core.exceptions import NotFoundException

# ── Chemins des ressources ─────────────────────────────────────────────────────
ASSETS_DIR = Path(__file__).parent.parent / "assets" / "report"

PAGE_W, PAGE_H = A4
MARGIN = 2.5 * cm
TEXT_W = PAGE_W - 2 * MARGIN

# ── Palette de couleurs ────────────────────────────────────────────────────────
BLACK       = colors.HexColor("#1A1A1A")
DARK        = colors.HexColor("#2C2C2C")
GREY        = colors.HexColor("#555555")
LIGHT       = colors.HexColor("#888888")
RULE        = colors.HexColor("#AAAAAA")
SABC_RED    = colors.HexColor("#C8102E")   # rouge SABC — bordure page de garde
SABC_RED_LIGHT = colors.HexColor("#E8304E") # rouge clair pour bordure intérieure
SABC_ORANGE = colors.HexColor("#F47920")   # orange SABC — accent
CODE_BG     = colors.HexColor("#F3F4F6")   # fond bloc code


# ══════════════════════════════════════════════════════════════════════════════
# Parseur HTML → Flowables ReportLab
# ══════════════════════════════════════════════════════════════════════════════

class _TipTapParser(HTMLParser):
    """
    Convertit le HTML produit par TipTap en une liste de Flowables ReportLab.
    Gère :
      - <p>, <br>                          → paragraphes / sauts de ligne
      - <strong>/<b>, <em>/<i>, <u>        → balises inline Times-Bold/Italic/souligné
      - <h1>, <h2>, <h3>                   → titres hiérarchiques
      - <ul>/<ol> + <li>                   → listes à puces / numérotées
      - <code>                             → texte monospace inline
      - <img src="data:image/...;base64,"> → images base64 extraites et insérées
      - <figure data-rimg>                 → conteneur image redimensionnable TipTap
    """

    def __init__(self, styles: dict, text_width: float):
        super().__init__()
        self._styles    = styles
        self._tw        = text_width
        self._flowables: list = []

        # État de l'inline buffer
        self._buf       = ""           # texte inline en cours
        self._bold      = 0
        self._italic    = 0
        self._underline = 0
        self._code_inline = 0

        # État des listes
        self._in_ul     = False
        self._in_ol     = False
        self._ol_counter = 0
        self._list_items: list = []

        # État heading
        self._heading_level = 0

        # Flag figure en cours (on ignore le reste jusqu'à </figure>)
        self._in_figure = False

    # ── helpers inline ────────────────────────────────────────────────────────

    def _flush_inline(self) -> str:
        """Renvoie le buffer inline accumulé et le vide."""
        text = self._buf.strip()
        self._buf = ""
        return text

    def _wrap_inline(self, text: str) -> str:
        """Applique les balises ReportLab selon le contexte inline actuel."""
        if not text:
            return text
        if self._bold and self._italic:
            text = f"<b><i>{text}</i></b>"
        elif self._bold:
            text = f"<b>{text}</b>"
        elif self._italic:
            text = f"<i>{text}</i>"
        if self._underline:
            text = f"<u>{text}</u>"
        if self._code_inline:
            text = f'<font name="Courier" size="9">{text}</font>'
        return text

    def _emit_paragraph(self, text: str, style_key: str = "body"):
        text = text.strip()
        if text:
            self._flowables.append(Paragraph(text, self._styles[style_key]))

    # ── tags de bloc ─────────────────────────────────────────────────────────

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)

        if tag == "figure":
            self._in_figure = True
            return

        if self._in_figure and tag == "img":
            src = attr_dict.get("src", "")
            if src.startswith("data:image"):
                img_fl = self._base64_image(src, attr_dict)
                if img_fl:
                    self._flowables.append(img_fl)
            return

        if tag in ("p", "div"):
            self._buf = ""

        elif tag in ("h1", "h2", "h3"):
            self._heading_level = int(tag[1])
            self._buf = ""

        elif tag in ("strong", "b"):
            self._bold += 1

        elif tag in ("em", "i"):
            self._italic += 1

        elif tag == "u":
            self._underline += 1

        elif tag == "code":
            self._code_inline += 1

        elif tag == "br":
            self._buf += "<br/>"

        elif tag == "ul":
            self._flush_inline()
            self._in_ul = True
            self._list_items = []

        elif tag == "ol":
            self._flush_inline()
            self._in_ol = True
            self._ol_counter = 0
            self._list_items = []

        elif tag == "li":
            self._buf = ""

        elif tag == "img" and not self._in_figure:
            src = attr_dict.get("src", "")
            if src.startswith("data:image"):
                img_fl = self._base64_image(src, attr_dict)
                if img_fl:
                    self._flowables.append(img_fl)

    def handle_endtag(self, tag):
        if tag == "figure":
            self._in_figure = False
            return

        if self._in_figure:
            return

        if tag in ("p", "div"):
            text = self._wrap_inline(self._flush_inline())
            self._emit_paragraph(text, "body")

        elif tag in ("h1", "h2", "h3"):
            text = self._wrap_inline(self._flush_inline())
            level = self._heading_level
            sk = {1: "comment_h1", 2: "comment_h2", 3: "comment_h3"}.get(level, "comment_h2")
            self._emit_paragraph(text, sk)
            self._heading_level = 0

        elif tag in ("strong", "b"):
            self._bold = max(0, self._bold - 1)

        elif tag in ("em", "i"):
            self._italic = max(0, self._italic - 1)

        elif tag == "u":
            self._underline = max(0, self._underline - 1)

        elif tag == "code":
            self._code_inline = max(0, self._code_inline - 1)

        elif tag == "li":
            text = self._wrap_inline(self._flush_inline())
            if text:
                self._list_items.append(text)

        elif tag == "ul":
            if self._list_items:
                items = [ListItem(Paragraph(f"• {t}", self._styles["body_no_indent"]), leftIndent=20)
                         for t in self._list_items]
                self._flowables.append(ListFlowable(items, bulletType="bullet",
                                                     leftIndent=10, spaceBefore=2, spaceAfter=2))
            self._in_ul = False
            self._list_items = []

        elif tag == "ol":
            if self._list_items:
                items = []
                for i, t in enumerate(self._list_items, 1):
                    items.append(ListItem(Paragraph(f"{i}. {t}", self._styles["body_no_indent"]),
                                          leftIndent=20))
                self._flowables.append(ListFlowable(items, bulletType="1",
                                                     leftIndent=10, spaceBefore=2, spaceAfter=2))
            self._in_ol = False
            self._list_items = []

    def handle_data(self, data: str):
        if self._in_figure:
            return
        self._buf += data.replace("<", "&lt;").replace(">", "&gt;")

    # ── image base64 ─────────────────────────────────────────────────────────

    def _base64_image(self, src: str, attrs: dict) -> Optional[Image]:
        """Décode une image base64 data-URI et retourne un Image ReportLab."""
        try:
            match = re.match(r"data:image/(\w+);base64,(.*)", src, re.DOTALL)
            if not match:
                return None
            fmt, b64data = match.group(1), match.group(2)
            raw = base64.b64decode(b64data)
            buf = io.BytesIO(raw)

            try:
                desired_w = min(float(attrs.get("width", self._tw * 0.70)), self._tw * 0.90)
            except (ValueError, TypeError):
                desired_w = self._tw * 0.70

            img = Image(buf, width=desired_w, kind="proportional")
            img.hAlign = attrs.get("align", "LEFT").upper()
            return img
        except Exception:
            return None

    # ── résultat ─────────────────────────────────────────────────────────────

    @property
    def flowables(self) -> list:
        leftover = self._wrap_inline(self._flush_inline())
        if leftover:
            self._flowables.append(Paragraph(leftover, self._styles["body"]))
        return self._flowables


def _html_to_flowables(html: str, styles: dict, text_width: float) -> list:
    """Convertit du HTML TipTap en liste de Flowables ReportLab."""
    if not html or not html.strip():
        return []
    p = _TipTapParser(styles, text_width)
    p.feed(html)
    return p.flowables


def _html_to_plain(html: str) -> str:
    """Extrait le texte brut (fallback simple)."""
    class _S(HTMLParser):
        def __init__(self):
            super().__init__(); self._p = []
        def handle_data(self, d): self._p.append(d)
        def handle_starttag(self, t, a):
            if t in ("p","br","li","div","h1","h2","h3"): self._p.append("\n")
        @property
        def text(self): return " ".join("".join(self._p).split())
    s = _S(); s.feed(html); return s.text.strip()


# ── Styles ─────────────────────────────────────────────────────────────────────

def _build_styles() -> dict:
    base = getSampleStyleSheet()

    return {
        # ── Page de garde ──────────────────────────────────────────────────────
        "cover_institution": ParagraphStyle(
            "cover_institution",
            fontName="Times-Roman", fontSize=10,
            textColor=BLACK, alignment=TA_CENTER,
            leading=14, spaceAfter=2,
        ),
        "cover_institution_bold": ParagraphStyle(
            "cover_institution_bold",
            fontName="Times-Bold", fontSize=10,
            textColor=BLACK, alignment=TA_CENTER,
            leading=14, spaceAfter=2,
        ),
        "cover_type": ParagraphStyle(
            "cover_type",
            fontName="Times-Bold", fontSize=13,
            textColor=BLACK, alignment=TA_CENTER,
            leading=18, spaceBefore=8, spaceAfter=4,
        ),
        "cover_diploma": ParagraphStyle(
            "cover_diploma",
            fontName="Times-Roman", fontSize=12,
            textColor=BLACK, alignment=TA_CENTER,
            leading=16, spaceAfter=2,
        ),
        "cover_specialty": ParagraphStyle(
            "cover_specialty",
            fontName="Times-Bold", fontSize=12,
            textColor=BLACK, alignment=TA_CENTER,
            leading=16, spaceAfter=2,
        ),
        "cover_title": ParagraphStyle(
            "cover_title",
            fontName="Times-Bold", fontSize=20,
            textColor=BLACK, alignment=TA_CENTER,
            leading=26, spaceBefore=10, spaceAfter=8,
        ),
        "cover_label": ParagraphStyle(
            "cover_label",
            fontName="Times-Italic", fontSize=11,
            textColor=BLACK, alignment=TA_LEFT,
            leading=16,
        ),
        "cover_value": ParagraphStyle(
            "cover_value",
            fontName="Times-Bold", fontSize=11,
            textColor=BLACK, alignment=TA_LEFT,
            leading=16,
        ),
        "cover_label_right": ParagraphStyle(
            "cover_label_right",
            fontName="Times-Italic", fontSize=11,
            textColor=BLACK, alignment=TA_RIGHT,
            leading=16,
        ),
        "cover_value_right": ParagraphStyle(
            "cover_value_right",
            fontName="Times-Bold", fontSize=11,
            textColor=BLACK, alignment=TA_RIGHT,
            leading=16,
        ),
        "cover_footer": ParagraphStyle(
            "cover_footer",
            fontName="Times-Roman", fontSize=10,
            textColor=BLACK, alignment=TA_CENTER,
            leading=14,
        ),
        # ── Corps du document ──────────────────────────────────────────────────
        "h1": ParagraphStyle(
            "h1",
            fontName="Times-Bold", fontSize=16,
            textColor=BLACK, alignment=TA_LEFT,
            spaceBefore=18, spaceAfter=8,
            leading=20,
        ),
        "h2": ParagraphStyle(
            "h2",
            fontName="Times-Bold", fontSize=13,
            textColor=BLACK, alignment=TA_LEFT,
            spaceBefore=12, spaceAfter=6,
            leading=17,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Times-Roman", fontSize=11,
            textColor=DARK, alignment=TA_JUSTIFY,
            spaceAfter=8, leading=17,
            firstLineIndent=0.5 * cm,
        ),
        "body_no_indent": ParagraphStyle(
            "body_no_indent",
            fontName="Times-Roman", fontSize=11,
            textColor=DARK, alignment=TA_JUSTIFY,
            spaceAfter=8, leading=17,
        ),
        "caption": ParagraphStyle(
            "caption",
            fontName="Times-Italic", fontSize=9,
            textColor=GREY, alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "toc_h1": ParagraphStyle(
            "toc_h1",
            fontName="Times-Bold", fontSize=11,
            textColor=BLACK, leading=16,
            leftIndent=0, spaceAfter=4,
        ),
        "toc_h2": ParagraphStyle(
            "toc_h2",
            fontName="Times-Roman", fontSize=10,
            textColor=DARK, leading=14,
            leftIndent=1 * cm, spaceAfter=2,
        ),
        "footer_style": ParagraphStyle(
            "footer_style",
            fontName="Times-Italic", fontSize=8,
            textColor=GREY, alignment=TA_CENTER,
        ),
        "last_page_tagline": ParagraphStyle(
            "last_page_tagline",
            fontName="Times-Roman", fontSize=12,
            textColor=GREY, alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "no_content": ParagraphStyle(
            "no_content",
            fontName="Times-Italic", fontSize=11,
            textColor=GREY, alignment=TA_CENTER,
            spaceAfter=8,
        ),
        # ── Styles commentaires riches (TipTap headings) ───────────────────────
        "comment_h1": ParagraphStyle(
            "comment_h1",
            fontName="Times-Bold", fontSize=13,
            textColor=BLACK, alignment=TA_LEFT,
            spaceBefore=10, spaceAfter=4, leading=18,
        ),
        "comment_h2": ParagraphStyle(
            "comment_h2",
            fontName="Times-Bold", fontSize=12,
            textColor=DARK, alignment=TA_LEFT,
            spaceBefore=8, spaceAfter=3, leading=16,
        ),
        "comment_h3": ParagraphStyle(
            "comment_h3",
            fontName="Times-BoldItalic", fontSize=11,
            textColor=DARK, alignment=TA_LEFT,
            spaceBefore=6, spaceAfter=2, leading=15,
        ),
    }


# ── Dessin de la bordure décorative de la page de garde ───────────────────────

def _draw_cover_border(canvas, doc):
    """
    Dessine une bordure décorative double sur la page de garde :
    - Cadre extérieur épais rouge SABC
    - Cadre intérieur fin rouge clair
    - Petits carrés décoratifs aux quatre coins
    - Filets de coins en croix
    """
    canvas.saveState()

    padding_outer = 0.8 * cm
    padding_inner = 1.1 * cm
    corner_size   = 0.4 * cm   # taille des ornements de coin
    gap           = 0.15 * cm  # espace entre les deux cadres

    x0 = padding_outer
    y0 = padding_outer
    w  = PAGE_W - 2 * padding_outer
    h  = PAGE_H - 2 * padding_outer

    # ── Cadre extérieur épais ─────────────────────────────────────────────────
    canvas.setStrokeColor(SABC_RED)
    canvas.setLineWidth(2.5)
    canvas.rect(x0, y0, w, h)

    # ── Cadre intérieur fin ───────────────────────────────────────────────────
    xi = padding_inner
    yi = padding_inner
    wi = PAGE_W - 2 * padding_inner
    hi = PAGE_H - 2 * padding_inner

    canvas.setStrokeColor(SABC_RED_LIGHT)
    canvas.setLineWidth(0.8)
    canvas.rect(xi, yi, wi, hi)

    # ── Ornements de coins (petits carrés pleins rouges) ──────────────────────
    canvas.setFillColor(SABC_RED)
    canvas.setStrokeColor(SABC_RED)

    corners = [
        (x0, y0),                   # bas-gauche
        (x0 + w - corner_size, y0), # bas-droite
        (x0, y0 + h - corner_size), # haut-gauche
        (x0 + w - corner_size, y0 + h - corner_size),  # haut-droite
    ]
    for (cx, cy) in corners:
        canvas.rect(cx, cy, corner_size, corner_size, fill=1, stroke=0)

    # ── Traits de coin en croix (décoratifs) entre les deux cadres ───────────
    canvas.setStrokeColor(SABC_RED)
    canvas.setLineWidth(1.0)
    tick = 0.9 * cm  # longueur des petits traits

    # Coin bas-gauche
    canvas.line(x0 + corner_size + gap, y0 + corner_size / 2,
                x0 + corner_size + tick, y0 + corner_size / 2)
    canvas.line(x0 + corner_size / 2, y0 + corner_size + gap,
                x0 + corner_size / 2, y0 + corner_size + tick)

    # Coin bas-droite
    canvas.line(x0 + w - corner_size - gap, y0 + corner_size / 2,
                x0 + w - corner_size - tick, y0 + corner_size / 2)
    canvas.line(x0 + w - corner_size / 2, y0 + corner_size + gap,
                x0 + w - corner_size / 2, y0 + corner_size + tick)

    # Coin haut-gauche
    canvas.line(x0 + corner_size + gap, y0 + h - corner_size / 2,
                x0 + corner_size + tick, y0 + h - corner_size / 2)
    canvas.line(x0 + corner_size / 2, y0 + h - corner_size - gap,
                x0 + corner_size / 2, y0 + h - corner_size - tick)

    # Coin haut-droite
    canvas.line(x0 + w - corner_size - gap, y0 + h - corner_size / 2,
                x0 + w - corner_size - tick, y0 + h - corner_size / 2)
    canvas.line(x0 + w - corner_size / 2, y0 + h - corner_size - gap,
                x0 + w - corner_size / 2, y0 + h - corner_size - tick)

    canvas.restoreState()


# ── Gestionnaire de pied de page ───────────────────────────────────────────────

def _make_footer_frame(doc_ref, total_pages_ref: list):
    """Retourne une fonction on_page qui dessine le pied de page."""
    def _draw_footer(canvas, doc):
        canvas.saveState()
        footer_text = "WakAgenda — Agenda interactif des stagiaires — Boissons du Cameroun"
        canvas.setFont("Times-Italic", 8)
        canvas.setFillColor(GREY)
        canvas.drawCentredString(
            PAGE_W / 2,
            1.5 * cm,
            footer_text,
        )
        # Numéro de page (sauf page de garde)
        if doc.page > 1:
            canvas.setFont("Times-Roman", 8)
            canvas.drawRightString(
                PAGE_W - MARGIN,
                1.5 * cm,
                f"{doc.page}",
            )
        # Filet de séparation
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.4)
        canvas.line(MARGIN, 1.8 * cm, PAGE_W - MARGIN, 1.8 * cm)
        canvas.restoreState()

    return _draw_footer


# ── Constructeur du rapport ────────────────────────────────────────────────────

class RapportTechnicoFonctionnel:
    """
    Génère le rapport technico-fonctionnel PDF à partir des données de l'utilisateur.
    """

    def __init__(self, db: Session):
        self.db        = db
        self.user_repo = UserRepository(db)
        self.task_repo = TaskRepository(db)

    def generate(
        self,
        user_id: uuid.UUID,
        date_from: Optional[date] = None,
        date_to:   Optional[date] = None,
    ) -> bytes:
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundException("Utilisateur")

        # Chargement des tâches avec domaines personnalisés et commentaires
        tasks: List[Task] = (
            self.db.query(Task)
            .options(joinedload(Task.custom_domain), joinedload(Task.comments))
            .filter(
                Task.user_id == user_id,
                Task.task_date >= (date_from or user.internship_start_date),
                Task.task_date <= (date_to   or date.today()),
            )
            .order_by(Task.task_date.asc(), Task.start_time.asc())
            .limit(10_000)
            .all()
        )

        styles = _build_styles()
        buffer = io.BytesIO()

        # ── Mise en page : deux templates (couverture + corps) ─────────────────
        cover_frame = Frame(
            MARGIN, MARGIN,
            TEXT_W, PAGE_H - 2 * MARGIN,
            id="cover_frame",
        )
        body_frame = Frame(
            MARGIN, 2.2 * cm,
            TEXT_W, PAGE_H - MARGIN - 2.2 * cm,
            id="body_frame",
        )

        footer_fn = _make_footer_frame(None, [])

        cover_template = PageTemplate(
            id="Cover",
            frames=[cover_frame],
            onPage=_draw_cover_border,  # Bordure décorative sur la page de garde
        )
        body_template = PageTemplate(
            id="Body",
            frames=[body_frame],
            onPage=footer_fn,
        )

        doc = BaseDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=MARGIN,
            rightMargin=MARGIN,
            topMargin=MARGIN,
            bottomMargin=2.2 * cm,
            title=f"Rapport technico-fonctionnel WakAgenda – {user.full_name}",
            author="WakAgenda – Boissons du Cameroun",
        )
        doc.addPageTemplates([cover_template, body_template])

        story = []

        # ── 1. Page de garde ───────────────────────────────────────────────────
        story += self._cover_page(user, styles, date_from, date_to)
        story.append(NextPageTemplate("Body"))
        story.append(PageBreak())

        # ── 2. Table des matières ──────────────────────────────────────────────
        story += self._toc_section(tasks, styles)
        story.append(PageBreak())

        # ── 3. Corps : domaines → chapitres, tâches → sections ────────────────
        story += self._body_section(tasks, styles)

        # ── 4. Dernière page (logo WakAgenda) ──────────────────────────────────
        story.append(PageBreak())
        story += self._last_page(styles)

        doc.build(story)
        return buffer.getvalue()

    # ── Page de garde ──────────────────────────────────────────────────────────

    def _cover_page(self, user, styles, date_from, date_to) -> list:
        """
        Reproduit fidèlement la structure du mémoire ENSPY/SABC :
          - Bandeau haut : logo ENSPY (gauche) | logo SABC (droite) — grands logos
          - Institutions (gauche) | Entreprise (droite)
          - Titre type document
          - Grand titre du rapport
          - Auteur (gauche) | Encadreurs (droite)
          - Pied : promotion / date / version
        """
        from reportlab.platypus import Table, TableStyle as TS

        elements = []
        s = styles

        # ── Logos (grands, bien visibles) ─────────────────────────────────────
        logo_enspy_path = ASSETS_DIR / "logo.png"
        logo_sabc_path  = ASSETS_DIR / "logo_sabc.png"

        logo_enspy_cell = Spacer(1, 3.5 * cm)
        logo_sabc_cell  = Spacer(1, 3.5 * cm)

        if logo_enspy_path.exists():
            # Logo ENSPY : 3.5 cm de hauteur pour bien le voir
            img_e = Image(str(logo_enspy_path), width=5 * cm, height=5 * cm,
                          kind="proportional")
            img_e.hAlign = "CENTER"
            logo_enspy_cell = img_e

        if logo_sabc_path.exists():
            # Logo SABC : 4.5 cm pour qu'il soit prédominant
            img_s = Image(str(logo_sabc_path), width=4.5 * cm, height=4.5 * cm,
                          kind="proportional")
            img_s.hAlign = "CENTER"
            logo_sabc_cell = img_s

        # Colonnes gauche / droite de la page de garde
        left_col = [
            logo_enspy_cell,
            Spacer(1, 0.0 * cm),
            Paragraph("République du Cameroun", s["cover_institution"]),
            Paragraph("Ministère de l'Enseignement Supérieur", s["cover_institution"]),
            Paragraph("Université de Yaoundé I", s["cover_institution"]),
            Paragraph("École Nationale Supérieure<br/>Polytechnique de Yaoundé", s["cover_institution_bold"]),
        ]
        right_col = [
            logo_sabc_cell,
            Spacer(1, 0.50 * cm),
            Paragraph("Société Anonyme des<br/><b>Boissons du Cameroun (SABC)</b>", s["cover_institution"]),
            Paragraph("Direction des Systèmes d'Information", s["cover_institution"]),
            Paragraph("Département Transformation Digitale,<br/>Organisation et Projets", s["cover_institution"]),
        ]

        header_tbl = Table(
            [[left_col, right_col]],
            colWidths=[TEXT_W / 2, TEXT_W / 2],
        )
        header_tbl.setStyle(TS([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN",  (0, 0), (0, 0),   "CENTER"),
            ("ALIGN",  (1, 0), (1, 0),   "CENTER"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        elements.append(header_tbl)
        elements.append(Spacer(1, 0.5 * cm))

        # ── Titre du document ──────────────────────────────────────────────────
        elements.append(Paragraph("Rapport Technico-Fonctionnel", s["cover_type"]))
        elements.append(Spacer(1, 0.1 * cm))
        elements.append(Paragraph(
            f"Période du {(date_from or user.internship_start_date).strftime('%d/%m/%Y')}"
            f" au {(date_to or date.today()).strftime('%d/%m/%Y')}",
            s["cover_diploma"],
        ))
        elements.append(Spacer(1, 0.4 * cm))

        # ── Grand titre ────────────────────────────────────────────────────────
        elements.append(HRFlowable(width="100%", thickness=0.5, color=SABC_RED_LIGHT))
        elements.append(Spacer(1, 0.15 * cm))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=SABC_RED))
        elements.append(Spacer(1, 0.5 * cm))
        elements.append(Paragraph(
            "RAPPORT D'ACTIVITÉ<br/>DU STAGIAIRE",
            s["cover_title"],
        ))
        elements.append(Spacer(1, 0.5 * cm))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=SABC_RED))
        elements.append(Spacer(1, 0.1 * cm))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=SABC_RED_LIGHT))
        elements.append(Spacer(1, 6 * cm))

        # ── Réalisé par / Encadré par ──────────────────────────────────────────
        left_author = [
            Paragraph("<i>Réalisé par :</i>", s["cover_label"]),
            Spacer(1, 0.15 * cm),
            Paragraph(user.full_name.upper(), s["cover_value"]),
            Spacer(1, 0.1 * cm),
            Paragraph(user.department, s["cover_value"]),
        ]
        right_author = [
            Paragraph("<i>Encadré par :</i>", s["cover_label_right"]),
            Spacer(1, 0.15 * cm),
            Paragraph(
                f"<b>M. {user.supervisor_name}</b><br/>Encadreur professionnel (SABC)",
                s["cover_value_right"],
            ),
        ]

        author_tbl = Table(
            [[left_author, right_author]],
            colWidths=[TEXT_W / 2, TEXT_W / 2],
        )
        author_tbl.setStyle(TS([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        elements.append(author_tbl)
        elements.append(Spacer(1, 1.5 * cm))

        # ── Pied de la page de garde ───────────────────────────────────────────
        elements.append(HRFlowable(width="100%", thickness=0.5, color=RULE))
        elements.append(Spacer(1, 0.3 * cm))

        footer_tbl = Table(
            [[
                Paragraph("Promotion 2026", s["cover_footer"]),
                Paragraph(
                    f"Généré le : {datetime.now(timezone.utc).strftime('%d %B %Y')}",
                    s["cover_footer"],
                ),
                Paragraph("Version : 1.0", s["cover_footer"]),
            ]],
            colWidths=[TEXT_W / 3] * 3,
        )
        footer_tbl.setStyle(TS([
            ("ALIGN", (0, 0), (0, 0), "LEFT"),
            ("ALIGN", (1, 0), (1, 0), "CENTER"),
            ("ALIGN", (2, 0), (2, 0), "RIGHT"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        elements.append(footer_tbl)

        return elements

    # ── Table des matières (manuelle, sans numérotation de pages dynamique) ────

    def _toc_section(self, tasks: List[Task], styles) -> list:
        elements = []
        elements.append(Paragraph("Table des matières", styles["h1"]))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=RULE))
        elements.append(Spacer(1, 0.4 * cm))

        # Regroupement par domaine
        domain_map: dict[str, list[Task]] = {}
        for task in tasks:
            domain = task.effective_domain_name
            domain_map.setdefault(domain, []).append(task)

        chap_num = 1
        for domain_name, domain_tasks in domain_map.items():
            elements.append(
                Paragraph(
                    f"{chap_num}. {domain_name}",
                    styles["toc_h1"],
                )
            )
            sec_num = 1
            for task in domain_tasks:
                elements.append(
                    Paragraph(
                        f"&nbsp;&nbsp;&nbsp;&nbsp;{chap_num}.{sec_num} "
                        f"{task.task_date.strftime('%d/%m/%Y')} — {task.title}",
                        styles["toc_h2"],
                    )
                )
                sec_num += 1
            chap_num += 1
            elements.append(Spacer(1, 0.15 * cm))

        return elements

    # ── Corps du document ──────────────────────────────────────────────────────

    def _body_section(self, tasks: List[Task], styles) -> list:
        elements = []

        # Regroupement par domaine
        domain_map: dict[str, list[Task]] = {}
        for task in tasks:
            domain = task.effective_domain_name
            domain_map.setdefault(domain, []).append(task)

        chap_num = 1
        for domain_name, domain_tasks in domain_map.items():
            # ── Titre du chapitre (domaine) ────────────────────────────────────
            elements.append(Paragraph(
                f"Chapitre {chap_num} — {domain_name}",
                styles["h1"],
            ))
            elements.append(HRFlowable(width="100%", thickness=0.6, color=RULE))
            elements.append(Spacer(1, 0.3 * cm))

            # Introduction du chapitre
            elements.append(Paragraph(
                f"Ce chapitre regroupe l'ensemble des activités réalisées dans le domaine "
                f"<b>{domain_name}</b> au cours de la période couverte par le présent rapport.",
                styles["body_no_indent"],
            ))
            elements.append(Spacer(1, 0.4 * cm))

            sec_num = 1
            for task in domain_tasks:
                block = self._task_block(chap_num, sec_num, task, styles)
                elements.append(KeepTogether(block[:4]))  # Titre + début du contenu ensemble
                elements += block[4:]
                sec_num += 1

            chap_num += 1
            elements.append(Spacer(1, 0.5 * cm))

        if not tasks:
            elements.append(Paragraph(
                "Aucune tâche enregistrée pour la période sélectionnée.",
                styles["no_content"],
            ))

        return elements

    def _task_block(self, chap: int, sec: int, task: Task, styles) -> list:
        """
        Construit le bloc d'une section (tâche) :
          - Titre de section (sans filet orange — supprimé)
          - Bandeau méta (date, horaire, catégorie, statut)
          - Contenu riche du commentaire (HTML TipTap) :
              bold, italic, listes, titres, images base64 inline
          - Image fichier optionnelle (ASSETS_DIR/tasks/<id>.png)
        """
        block = []

        # ── Titre de section ───────────────────────────────────────────────────
        block.append(Paragraph(
            f"{chap}.{sec} &nbsp; {task.title}",
            styles["h2"],
        ))
        # NOTE : filet orange sous le titre de section SUPPRIMÉ (comme demandé)

        # ── Bandeau méta ───────────────────────────────────────────────────────
        date_str  = task.task_date.strftime("%A %d %B %Y").capitalize()
        heure_str = f"{task.start_time.strftime('%H:%M')} — {task.end_time.strftime('%H:%M')}"
        try:
            duration = (
                datetime.combine(task.task_date, task.end_time) -
                datetime.combine(task.task_date, task.start_time)
            ).seconds // 60
            dur_str = f"{duration // 60}h{duration % 60:02d}"
        except Exception:
            dur_str = ""

        meta = (
            f"<b>Date :</b> {date_str} &nbsp;|&nbsp; "
            f"<b>Horaire :</b> {heure_str}"
            + (f" ({dur_str})" if dur_str else "")
            + f" &nbsp;|&nbsp; <b>Catégorie :</b> {task.category.value}"
            f" &nbsp;|&nbsp; <b>Statut :</b> {task.status.value}"
        )
        block.append(Paragraph(meta, styles["body_no_indent"]))
        block.append(Spacer(1, 0.25 * cm))

        # ── Description (si présente et pas de commentaire) ───────────────────
        comment = task.comments[0] if task.comments else None

        if task.description and not comment:
            desc_flows = _html_to_flowables(task.description, styles, TEXT_W)
            if desc_flows:
                block.extend(desc_flows)
            else:
                plain = _html_to_plain(task.description)
                if plain:
                    block.append(Paragraph(plain, styles["body"]))

        # ── Commentaire riche (HTML TipTap) ───────────────────────────────────
        if comment and comment.content and comment.content.strip():
            rich_flows = _html_to_flowables(comment.content, styles, TEXT_W)
            if rich_flows:
                block.extend(rich_flows)
            else:
                # Fallback texte brut
                plain = _html_to_plain(comment.content)
                if plain:
                    block.append(Paragraph(plain, styles["body"]))
        elif not task.description:
            block.append(Paragraph(
                "Aucun commentaire renseigné pour cette activité.",
                styles["no_content"],
            ))

        # ── Image fichier optionnelle (ASSETS_DIR/tasks/<task_id>.*) ─────────
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            img_path = ASSETS_DIR / "tasks" / f"{task.id}{ext}"
            if img_path.exists():
                img = Image(str(img_path), width=TEXT_W * 0.70, kind="proportional")
                block.append(Spacer(1, 0.3 * cm))
                block.append(img)
                block.append(Paragraph(
                    f"Figure {chap}.{sec} — {task.title}",
                    styles["caption"],
                ))
                break

        block.append(Spacer(1, 0.6 * cm))
        return block

    # ── Dernière page ──────────────────────────────────────────────────────────

    def _last_page(self, styles) -> list:
        """
        Dernière page avec logo WakAgenda très grand et parfaitement centré.
        """
        elements = []
        elements.append(Spacer(1, 2.5 * cm))

        logo_path = ASSETS_DIR / "logo.png"
        if logo_path.exists():
            # Logo très grand : 9 cm de largeur, centré
            img = Image(str(logo_path), width=9 * cm, height=9 * cm, kind="proportional")
            img.hAlign = "CENTER"
            elements.append(img)
            elements.append(Spacer(1, 0.8 * cm))

        elements.append(Paragraph("Agenda interactif des stagiaires", ParagraphStyle(
            "last_brand",
            fontName="Times-Bold", fontSize=28,
            textColor=BLACK, alignment=TA_CENTER,
            spaceAfter=8,
        )))
        elements.append(Spacer(1, 0.6 * cm))
        elements.append(HRFlowable(width="50%", thickness=0.8, color=SABC_RED, hAlign="CENTER"))
        elements.append(Spacer(1, 0.6 * cm))
        elements.append(Paragraph(
            "Boissons du Cameroun — Direction des Systèmes d'Information<br/>"
            "Département Transformation Digitale, Organisation et Projets<br/>"
            "77, rue Prince Bell — Bali, Douala",
            styles["last_page_tagline"],
        ))
        elements.append(Spacer(1, 0.4 * cm))
        elements.append(Paragraph(
            f"Rapport généré le {datetime.now(timezone.utc).strftime('%d/%m/%Y à %H:%M')} UTC",
            ParagraphStyle(
                "last_date",
                fontName="Times-Italic", fontSize=9,
                textColor=LIGHT, alignment=TA_CENTER,
            ),
        ))
        return elements


# ── Service exposé ─────────────────────────────────────────────────────────────

class RapportTechnicoFonctionnelService:
    def __init__(self, db: Session):
        self._builder = RapportTechnicoFonctionnel(db)

    def generate_pdf(
        self,
        user_id: uuid.UUID,
        date_from: Optional[date] = None,
        date_to:   Optional[date] = None,
    ) -> bytes:
        return self._builder.generate(user_id, date_from, date_to)