"""
app/services/email_service.py

Service d'envoi d'emails transactionnels via SMTP Gmail.
Expéditeur : wakagenda@gmail.com (App Password requis)

Configuration requise dans .env / variables Render :
  SMTP_HOST     = smtp.gmail.com
  SMTP_PORT     = 465
  SMTP_USER     = wakagenda@gmail.com
  SMTP_PASSWORD = <app password 16 chars>
  SMTP_FROM     = WakAgenda <wakagenda@gmail.com>
  SMTP_USE_TLS  = true          ← SSL direct sur port 465
"""

import smtplib
import ssl
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, date, time
from typing import Optional

from app.core.config import settings

log = logging.getLogger("wakagenda.email")

# ── Palette couleurs WakAgenda ─────────────────────────────────────────────────
_PRIMARY  = "#C0392B"
_DARK     = "#1A1A2E"
_GREY     = "#7F8C8D"
_LIGHT_BG = "#F4F6F8"
_WHITE    = "#FFFFFF"
_SUCCESS  = "#27AE60"
_DANGER   = "#E74C3C"
_BORDER   = "#E0E0E0"


# ══════════════════════════════════════════════════════════════════════════════
# Template HTML de base
# ══════════════════════════════════════════════════════════════════════════════

def _base_template(title: str, body_html: str, cta_buttons: str = "") -> str:
    year = datetime.now().year
    cta_block = (
        f'<div class="divider"></div><div class="cta-row">{cta_buttons}</div>'
        if cta_buttons else ""
    )
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{title}</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:{_LIGHT_BG};font-family:'Segoe UI',Arial,sans-serif;color:{_DARK}}}
    .wrapper{{max-width:600px;margin:40px auto;background:{_WHITE};border-radius:8px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08)}}
    .header{{background:{_PRIMARY};padding:32px 40px;text-align:center}}
    .brand{{font-size:22px;font-weight:700;color:{_WHITE};letter-spacing:1px;text-transform:uppercase}}
    .tagline{{font-size:12px;color:rgba(255,255,255,.75);margin-top:4px}}
    .body{{padding:40px}}
    .body h1{{font-size:20px;font-weight:700;color:{_DARK};margin-bottom:16px;border-left:3px solid {_PRIMARY};padding-left:12px}}
    .body p{{font-size:14px;line-height:1.75;color:#4A4A4A;margin-bottom:12px}}
    .info-card{{background:{_LIGHT_BG};border:1px solid {_BORDER};border-radius:6px;padding:20px 24px;margin:24px 0}}
    .info-card table{{width:100%;border-collapse:collapse}}
    .info-card td{{padding:6px 0;font-size:13px;vertical-align:top}}
    .info-card td:first-child{{color:{_GREY};width:38%;font-weight:600;text-transform:uppercase;font-size:11px;letter-spacing:.4px}}
    .info-card td:last-child{{color:{_DARK};font-weight:500}}
    .divider{{height:1px;background:{_BORDER};margin:24px 0}}
    .cta-row{{text-align:center;margin:32px 0 16px}}
    .btn{{display:inline-block;padding:13px 32px;border-radius:5px;font-size:14px;font-weight:600;text-decoration:none;letter-spacing:.3px;margin:0 8px}}
    .btn-accept{{background:{_SUCCESS};color:{_WHITE}}}
    .btn-cancel{{background:{_WHITE};color:{_DANGER};border:1.5px solid {_DANGER}}}
    .footer{{background:{_LIGHT_BG};border-top:1px solid {_BORDER};padding:20px 40px;text-align:center}}
    .footer p{{font-size:11px;color:{_GREY};line-height:1.6}}
    .footer strong{{color:{_PRIMARY}}}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <div class="brand">WakAgenda</div>
      <div class="tagline">Agenda interactif des stagiaires — Boissons du Cameroun</div>
    </div>
    <div class="body">
      {body_html}
      {cta_block}
    </div>
    <div class="footer">
      <p>Ce message est envoyé automatiquement par <strong>WakAgenda</strong>.<br/>
      Merci de ne pas répondre directement à cet email.</p>
      <p style="margin-top:8px;">Boissons du Cameroun — DSI — 77, rue Prince Bell, Bali, Douala &nbsp;|&nbsp; &copy; {year} WakAgenda</p>
    </div>
  </div>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════════════
# Corps des emails
# ══════════════════════════════════════════════════════════════════════════════

def _reminder_body(
    first_name: str,
    task_title: str,
    task_date: date,
    start_time: time,
    end_time: time,
    category: str,
    domain: str,
    description: Optional[str],
    minutes_before: int,
) -> str:
    if minutes_before >= 1440:
        delay_label = "demain"
    elif minutes_before >= 60:
        h = minutes_before // 60
        delay_label = f"dans {h} heure{'s' if h > 1 else ''}"
    else:
        delay_label = f"dans {minutes_before} minutes"

    desc_row = f"<tr><td>Description</td><td>{description}</td></tr>" if description else ""
    return f"""
<h1>Rappel de tâche</h1>
<p>Bonjour <strong>{first_name}</strong>,</p>
<p>Votre tâche planifiée commence <strong>{delay_label}</strong>. Voici les détails :</p>
<div class="info-card">
  <table>
    <tr><td>Intitulé</td><td>{task_title}</td></tr>
    <tr><td>Date</td><td>{task_date.strftime('%A %d %B %Y').capitalize()}</td></tr>
    <tr><td>Horaire</td><td>{start_time.strftime('%H:%M')} — {end_time.strftime('%H:%M')}</td></tr>
    <tr><td>Catégorie</td><td>{category}</td></tr>
    <tr><td>Domaine</td><td>{domain}</td></tr>
    {desc_row}
  </table>
</div>
<p>Confirmez votre prise en charge en cliquant sur <em>Accepter</em>, ou annulez si vous n'êtes pas disponible.</p>
"""


def _start_notification_body(
    first_name: str,
    task_title: str,
    task_date: date,
    start_time: time,
    end_time: time,
    category: str,
    domain: str,
) -> str:
    return f"""
<h1>Votre tâche commence maintenant</h1>
<p>Bonjour <strong>{first_name}</strong>,</p>
<p>La tâche suivante vient de débuter. Confirmez votre prise en charge.</p>
<div class="info-card">
  <table>
    <tr><td>Intitulé</td><td>{task_title}</td></tr>
    <tr><td>Date</td><td>{task_date.strftime('%A %d %B %Y').capitalize()}</td></tr>
    <tr><td>Horaire</td><td>{start_time.strftime('%H:%M')} — {end_time.strftime('%H:%M')}</td></tr>
    <tr><td>Catégorie</td><td>{category}</td></tr>
    <tr><td>Domaine</td><td>{domain}</td></tr>
  </table>
</div>
"""


# ══════════════════════════════════════════════════════════════════════════════
# Envoi bas niveau — Gmail SSL port 465
# ══════════════════════════════════════════════════════════════════════════════

def _send(to: str, subject: str, html: str) -> None:
    """
    Envoi SMTP réel.
    - Port 465  → SMTP_SSL  (SSL dès la connexion)   ← Gmail recommande ça
    - Port 587  → SMTP + STARTTLS
    Lit SMTP_USE_TLS depuis les settings :
      true  → port 465, SMTP_SSL
      false → port 587, STARTTLS
    """
    smtp_host = settings.SMTP_HOST
    smtp_port = settings.SMTP_PORT
    smtp_user = settings.SMTP_USER
    smtp_pass = settings.SMTP_PASSWORD
    from_addr = settings.SMTP_FROM or f"WakAgenda <{smtp_user}>"
    use_tls   = settings.SMTP_USE_TLS  # true = SSL direct (port 465)

    if not smtp_host or not smtp_user or not smtp_pass:
        log.warning(
            "SMTP non configuré (SMTP_HOST/SMTP_USER/SMTP_PASSWORD manquants). "
            "Email à %s non envoyé.", to
        )
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"]  = subject
    msg["From"]     = from_addr
    msg["To"]       = to
    msg["Reply-To"] = from_addr
    msg.attach(MIMEText(html, "html", "utf-8"))

    context = ssl.create_default_context()

    try:
        if use_tls:
            # Gmail port 465 — SSL direct
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
                server.login(smtp_user, smtp_pass)
                server.sendmail(from_addr, [to], msg.as_string())
        else:
            # Port 587 — STARTTLS
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(smtp_user, smtp_pass)
                server.sendmail(from_addr, [to], msg.as_string())

        log.info("Email envoyé à %s — %s", to, subject)

    except smtplib.SMTPAuthenticationError:
        log.error(
            "Échec authentification SMTP pour %s. "
            "Vérifiez SMTP_USER et SMTP_PASSWORD (App Password Gmail requis).", smtp_user
        )
        raise
    except smtplib.SMTPException as exc:
        log.error("Erreur SMTP envoi à %s : %s", to, exc)
        raise
    except Exception as exc:
        log.error("Erreur inattendue envoi email à %s : %s", to, exc)
        raise


# ══════════════════════════════════════════════════════════════════════════════
# Service public
# ══════════════════════════════════════════════════════════════════════════════

class EmailService:
    """Wrapper haut niveau — utilisé par le scheduler et le broadcast."""

    def send_reminder(
        self,
        to: str,
        first_name: str,
        task_title: str,
        task_date: date,
        start_time: time,
        end_time: time,
        category: str,
        domain: str,
        description: Optional[str],
        accept_url: str,
        cancel_url: str,
        minutes_before: int,
    ) -> None:
        body = _reminder_body(
            first_name, task_title, task_date, start_time,
            end_time, category, domain, description, minutes_before,
        )
        cta = (
            f'<a href="{accept_url}" class="btn btn-accept">Accepter la tâche</a>'
            f'<a href="{cancel_url}" class="btn btn-cancel">Annuler</a>'
        )
        if minutes_before < 60:
            delay_label = f"{minutes_before} min avant"
        elif minutes_before == 60:
            delay_label = "1h avant"
        else:
            delay_label = "La veille"
        subject = f"[WakAgenda] Rappel — {task_title} ({delay_label})"
        _send(to, subject, _base_template(subject, body, cta))

    def send_start_notification(
        self,
        to: str,
        first_name: str,
        task_title: str,
        task_date: date,
        start_time: time,
        end_time: time,
        category: str,
        domain: str,
        accept_url: str,
        cancel_url: str,
    ) -> None:
        body = _start_notification_body(
            first_name, task_title, task_date, start_time, end_time, category, domain,
        )
        cta = (
            f'<a href="{accept_url}" class="btn btn-accept">Accepter la tâche</a>'
            f'<a href="{cancel_url}" class="btn btn-cancel">Annuler</a>'
        )
        subject = f"[WakAgenda] Début de tâche — {task_title}"
        _send(to, subject, _base_template(subject, body, cta))

    def send_broadcast(self, to: str, subject: str, html_body: str) -> None:
        """Utilisé par la route /notifications/broadcast."""
        _send(to, subject, html_body)


# Singleton
email_service = EmailService()