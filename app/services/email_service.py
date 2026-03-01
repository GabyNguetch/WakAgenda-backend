"""
app/services/email_service.py
Service d'envoi d'emails transactionnels via SMTP.
Principe SOLID : Single Responsibility – ce service gère uniquement les emails.
Templates HTML modernes et professionnels, sans icônes ni emojis.
Expéditeur fixe : noreply@wakagenda.com
"""

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, date, time
from typing import Optional

from app.core.config import settings


# ── Palette couleurs WakAgenda ─────────────────────────────────────────────────
_PRIMARY     = "#C0392B"
_DARK        = "#1A1A2E"
_GREY        = "#7F8C8D"
_LIGHT_BG    = "#F4F6F8"
_WHITE       = "#FFFFFF"
_SUCCESS     = "#27AE60"
_DANGER      = "#E74C3C"
_BORDER      = "#E0E0E0"


def _base_template(title: str, body_html: str, cta_buttons: str = "") -> str:
    """
    Gabarit de base pour tous les emails WakAgenda.
    Aucun emoji, aucune icône — typographie et espacement suffisent.
    """
    year = datetime.now().year
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background-color: {_LIGHT_BG}; font-family: 'Segoe UI', Arial, sans-serif; color: {_DARK}; }}
    .wrapper {{ max-width: 600px; margin: 40px auto; background: {_WHITE}; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
    .header {{ background-color: {_PRIMARY}; padding: 32px 40px; text-align: center; }}
    .header .brand {{ font-size: 22px; font-weight: 700; color: {_WHITE}; letter-spacing: 1px; text-transform: uppercase; }}
    .header .tagline {{ font-size: 12px; color: rgba(255,255,255,0.75); margin-top: 4px; letter-spacing: 0.5px; }}
    .body {{ padding: 40px; }}
    .body h1 {{ font-size: 20px; font-weight: 700; color: {_DARK}; margin-bottom: 16px; border-left: 3px solid {_PRIMARY}; padding-left: 12px; }}
    .body p {{ font-size: 14px; line-height: 1.75; color: #4A4A4A; margin-bottom: 12px; }}
    .info-card {{ background: {_LIGHT_BG}; border: 1px solid {_BORDER}; border-radius: 6px; padding: 20px 24px; margin: 24px 0; }}
    .info-card table {{ width: 100%; border-collapse: collapse; }}
    .info-card td {{ padding: 6px 0; font-size: 13px; vertical-align: top; }}
    .info-card td:first-child {{ color: {_GREY}; width: 38%; font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.4px; }}
    .info-card td:last-child {{ color: {_DARK}; font-weight: 500; }}
    .divider {{ height: 1px; background: {_BORDER}; margin: 24px 0; }}
    .cta-row {{ text-align: center; margin: 32px 0 16px; }}
    .btn {{ display: inline-block; padding: 13px 32px; border-radius: 5px; font-size: 14px; font-weight: 600; text-decoration: none; letter-spacing: 0.3px; margin: 0 8px; }}
    .btn-accept {{ background-color: {_SUCCESS}; color: {_WHITE}; }}
    .btn-cancel {{ background-color: {_WHITE}; color: {_DANGER}; border: 1.5px solid {_DANGER}; }}
    .footer {{ background: {_LIGHT_BG}; border-top: 1px solid {_BORDER}; padding: 20px 40px; text-align: center; }}
    .footer p {{ font-size: 11px; color: {_GREY}; line-height: 1.6; }}
    .footer strong {{ color: {_PRIMARY}; }}
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
      {('<div class="divider"></div><div class="cta-row">' + cta_buttons + '</div>') if cta_buttons else ''}
    </div>
    <div class="footer">
      <p>Ce message est envoyé automatiquement par <strong>WakAgenda</strong>.<br/>
      Merci de ne pas répondre à cet email — <strong>noreply@wakagenda.com</strong></p>
      <p style="margin-top:8px;">Boissons du Cameroun — DSI — 77, rue Prince Bell, Bali, Douala &nbsp;|&nbsp; &copy; {year} WakAgenda</p>
    </div>
  </div>
</body>
</html>"""


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
    """Corps HTML d'un email de rappel."""
    delay_label = "dans 5 minutes" if minutes_before == 5 else f"dans {minutes_before} minutes"
    if minutes_before >= 60:
        h = minutes_before // 60
        delay_label = f"dans {h} heure{'s' if h > 1 else ''}"
    elif minutes_before >= 1440:
        delay_label = "demain"

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
<p>Veuillez confirmer votre prise en charge en cliquant sur le bouton <em>Accepter</em> ci-dessous, ou annuler si vous n'êtes pas disponible.</p>
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
    """Corps HTML du mail envoyé à l'heure exacte de début."""
    return f"""
<h1>Votre tâche commence maintenant</h1>
<p>Bonjour <strong>{first_name}</strong>,</p>
<p>La tâche suivante vient de débuter. Si ce n'est pas encore fait, confirmez votre prise en charge.</p>
<div class="info-card">
  <table>
    <tr><td>Intitulé</td><td>{task_title}</td></tr>
    <tr><td>Date</td><td>{task_date.strftime('%A %d %B %Y').capitalize()}</td></tr>
    <tr><td>Horaire</td><td>{start_time.strftime('%H:%M')} — {end_time.strftime('%H:%M')}</td></tr>
    <tr><td>Catégorie</td><td>{category}</td></tr>
    <tr><td>Domaine</td><td>{domain}</td></tr>
  </table>
</div>
<p>Si vous avez déjà accepté cette tâche, vous pouvez ignorer ce message.</p>
"""


class EmailService:
    """
    Service d'envoi d'emails transactionnels WakAgenda.
    Utilise SMTP configuré dans Settings.
    """

    def __init__(self) -> None:
        self._host   = settings.SMTP_HOST
        self._port   = settings.SMTP_PORT
        self._user   = settings.SMTP_USER
        self._pass   = settings.SMTP_PASSWORD
        self._from   = "WakAgenda <noreply@wakagenda.com>"
        self._use_tls = settings.SMTP_USE_TLS

    def _send(self, to: str, subject: str, html: str) -> None:
        """Envoi bas-niveau via SMTP."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = self._from
        msg["To"]      = to
        msg["Reply-To"] = "noreply@wakagenda.com"
        msg.attach(MIMEText(html, "html", "utf-8"))

        context = ssl.create_default_context()
        try:
            if self._use_tls:
                with smtplib.SMTP_SSL(self._host, self._port, context=context) as server:
                    server.login(self._user, self._pass)
                    server.sendmail(self._from, to, msg.as_string())
            else:
                with smtplib.SMTP(self._host, self._port) as server:
                    server.ehlo()
                    server.starttls(context=context)
                    server.login(self._user, self._pass)
                    server.sendmail(self._from, to, msg.as_string())
        except Exception as exc:  # pragma: no cover
            # En production, logger l'erreur sans la propager
            import logging
            logging.getLogger("wakagenda.email").error(
                "Échec d'envoi email à %s : %s", to, exc
            )

    # ── API Publique ───────────────────────────────────────────────────────────

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
        delay_label = f"{minutes_before} min avant" if minutes_before < 60 else (
            "1h avant" if minutes_before == 60 else "La veille"
        )
        subject = f"[WakAgenda] Rappel — {task_title} ({delay_label})"
        html = _base_template(subject, body, cta)
        self._send(to, subject, html)

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
        html = _base_template(subject, body, cta)
        self._send(to, subject, html)


# Singleton
email_service = EmailService()