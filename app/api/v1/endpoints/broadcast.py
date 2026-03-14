"""
app/api/v1/endpoints/broadcast.py
Route : POST /api/v1/notifications/broadcast
Envoie un email HTML à tous les utilisateurs actifs via EmailService (Gmail SMTP).
"""

import logging
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.email_service import email_service, _base_template

router = APIRouter(prefix="/notifications", tags=["Notifications"])
log    = logging.getLogger("wakagenda.broadcast")


class BroadcastRequest(BaseModel):
    subject: str
    message: str   # Texte brut ou HTML — sera enveloppé dans le template WakAgenda


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
    Envoie data.message à tous les utilisateurs actifs via Gmail SMTP.
    Le message est enveloppé dans le template HTML WakAgenda.
    Retourne : { sent, failed, recipients }
    """
    active_users: List[User] = (
        db.query(User).filter(User.is_active == True).all()
    )

    # Envelopper dans le template maison
    body_html = (
        data.message
        if "<" in data.message
        else f"<h1>{data.subject}</h1><p>{data.message}</p>"
    )
    html = _base_template(data.subject, body_html)

    sent:       int        = 0
    failed:     int        = 0
    recipients: List[str]  = []

    for user in active_users:
        try:
            email_service.send_broadcast(user.email, data.subject, html)
            sent += 1
            recipients.append(user.email)
        except Exception as exc:
            failed += 1
            log.error("Échec broadcast à %s : %s", user.email, exc)

    return {
        "sent":       sent,
        "failed":     failed,
        "recipients": recipients,
    }