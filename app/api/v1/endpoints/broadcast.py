"""
app/api/v1/endpoints/broadcast.py
Route : POST /api/v1/notifications/broadcast
Envoie un email à tous les utilisateurs actifs via smtplib.
"""

import smtplib
import ssl
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.core.config import settings

router = APIRouter(prefix="/notifications", tags=["Notifications"])

log = logging.getLogger("wakagenda.broadcast")


class BroadcastRequest(BaseModel):
    subject: str
    message: str  # Texte brut ou HTML


def _send_email(to: str, subject: str, html_body: str) -> None:
    """Envoie un email SMTP. Lève une exception en cas d'échec."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"]      = to
    msg["Reply-To"] = settings.SMTP_FROM or settings.SMTP_USER

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    context = ssl.create_default_context()

    if getattr(settings, "SMTP_USE_TLS", False):
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context) as server:
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(msg["From"], to, msg.as_string())
    else:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=context)
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(msg["From"], to, msg.as_string())


@router.post(
    "/broadcast",
    summary="Envoyer un email à tous les utilisateurs actifs",
)
def broadcast_notification(
    data: BroadcastRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Envoie data.message (HTML ou texte) à tous les utilisateurs actifs.
    Retourne : { sent, failed, recipients }
    """
    active_users: List[User] = (
        db.query(User).filter(User.is_active == True).all()
    )

    sent       = 0
    failed     = 0
    recipients: List[str] = []

    for user in active_users:
        try:
            _send_email(user.email, data.subject, data.message)
            sent += 1
            recipients.append(user.email)
            log.info("Broadcast envoyé à %s", user.email)
        except Exception as exc:
            failed += 1
            log.error("Échec broadcast à %s : %s", user.email, exc)

    return {
        "sent":       sent,
        "failed":     failed,
        "recipients": recipients,
    }