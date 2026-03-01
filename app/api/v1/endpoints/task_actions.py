"""
app/api/v1/endpoints/task_actions.py
Routes publiques (sans JWT) pour les actions email : accepter / annuler une tâche.
Accessibles depuis les boutons CTA des emails envoyés par le scheduler.
"""

from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from fastapi import Depends

from app.db.session import get_db
from app.models.task import Task, TaskStatus
from app.services.scheduler_service import cancel_task_jobs

router = APIRouter(prefix="/tasks/action", tags=["Actions Email (public)"])

# ── Palette WakAgenda ──────────────────────────────────────────────────────────
_PRIMARY = "#C0392B"
_DARK    = "#1A1A2E"
_GREY    = "#7F8C8D"
_LIGHT   = "#F4F6F8"
_GREEN   = "#27AE60"
_WHITE   = "#FFFFFF"


def _html_page(title: str, heading: str, message: str, color: str = _GREEN) -> str:
    """Génère une page HTML sobre aux couleurs WakAgenda."""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{title} — WakAgenda</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Segoe UI', Arial, sans-serif;
      background: {_LIGHT};
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      color: {_DARK};
    }}
    .card {{
      background: {_WHITE};
      border-radius: 10px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.10);
      padding: 48px 56px;
      max-width: 480px;
      width: 90%;
      text-align: center;
    }}
    .brand {{
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 2px;
      text-transform: uppercase;
      color: {_PRIMARY};
      margin-bottom: 32px;
    }}
    .indicator {{
      width: 64px;
      height: 64px;
      border-radius: 50%;
      background: {color};
      margin: 0 auto 24px;
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .indicator svg {{
      width: 32px;
      height: 32px;
      fill: none;
      stroke: {_WHITE};
      stroke-width: 2.5;
      stroke-linecap: round;
      stroke-linejoin: round;
    }}
    h1 {{
      font-size: 20px;
      font-weight: 700;
      margin-bottom: 12px;
      color: {_DARK};
    }}
    p {{
      font-size: 14px;
      line-height: 1.75;
      color: {_GREY};
    }}
    .footer {{
      margin-top: 40px;
      font-size: 11px;
      color: #BDBDBD;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="brand">WakAgenda</div>
    <div class="indicator">
      <svg viewBox="0 0 24 24">
        {"<polyline points='20 6 9 17 4 12'/>" if color == _GREEN else "<line x1='18' y1='6' x2='6' y2='18'/><line x1='6' y1='6' x2='18' y2='18'/>"}
      </svg>
    </div>
    <h1>{heading}</h1>
    <p>{message}</p>
    <div class="footer">Boissons du Cameroun — DSI &nbsp;|&nbsp; WakAgenda</div>
  </div>
</body>
</html>"""


# ── Accept ─────────────────────────────────────────────────────────────────────

@router.get(
    "/accept/{accept_token}",
    response_class=HTMLResponse,
    summary="Accepter une tâche via lien email (public)",
    include_in_schema=False,
)
def accept_task(accept_token: str, db: Session = Depends(get_db)) -> HTMLResponse:
    """
    Route publique appelée depuis le bouton « Accepter » dans l'email de rappel.
    - Si la tâche existe, n'est pas encore acceptée et son heure de fin n'est pas passée :
      → accepted_at = maintenant, status = DONE, annulation du job MISSED.
    - Sinon : message explicatif.
    """
    task: Task | None = (
        db.query(Task).filter(Task.accept_token == accept_token).first()
    )

    if not task:
        return HTMLResponse(
            content=_html_page(
                "Lien invalide",
                "Lien invalide",
                "Ce lien d'acceptation est introuvable ou a déjà expiré.",
                _PRIMARY,
            ),
            status_code=404,
        )

    now = datetime.now(timezone.utc)
    end_dt = datetime.combine(task.task_date, task.end_time).replace(tzinfo=timezone.utc)

    if end_dt < now:
        return HTMLResponse(
            content=_html_page(
                "Délai dépassé",
                "Délai dépassé",
                f"La tâche « {task.title} » est terminée depuis le "
                f"{task.task_date.strftime('%d/%m/%Y')} à {task.end_time.strftime('%H:%M')}. "
                "Il n'est plus possible de l'accepter.",
                _PRIMARY,
            ),
            status_code=200,
        )

    if task.accepted_at is not None:
        return HTMLResponse(
            content=_html_page(
                "Déjà acceptée",
                "Tâche déjà acceptée",
                f"Vous avez déjà confirmé la tâche « {task.title} » le "
                f"{task.accepted_at.strftime('%d/%m/%Y à %H:%M')} UTC.",
                _GREEN,
            ),
            status_code=200,
        )

    # Acceptation effective
    task.accepted_at = now
    task.status = TaskStatus.DONE
    db.commit()

    # Annuler le job MISSED qui n'a plus lieu d'être
    try:
        from app.services.scheduler_service import get_scheduler, _safe_remove_job
        _safe_remove_job(get_scheduler(), f"missed_{task.id}")
    except Exception:
        pass

    return HTMLResponse(
        content=_html_page(
            "Tâche acceptée",
            "Tâche confirmée",
            f"Votre tâche « {task.title} » du {task.task_date.strftime('%d/%m/%Y')} "
            f"({task.start_time.strftime('%H:%M')} — {task.end_time.strftime('%H:%M')}) "
            "a bien été marquée comme terminée. Merci !",
            _GREEN,
        ),
        status_code=200,
    )


# ── Cancel ─────────────────────────────────────────────────────────────────────

@router.get(
    "/cancel/{cancel_token}",
    response_class=HTMLResponse,
    summary="Annuler une tâche via lien email (public)",
    include_in_schema=False,
)
def cancel_task(cancel_token: str, db: Session = Depends(get_db)) -> HTMLResponse:
    """
    Route publique appelée depuis le bouton « Annuler » dans l'email de rappel.
    - Si la tâche n'est pas déjà DONE ou MISSED → status = CANCELLED, cancel_task_jobs().
    - Sinon : message explicatif.
    """
    task: Task | None = (
        db.query(Task).filter(Task.cancel_token == cancel_token).first()
    )

    if not task:
        return HTMLResponse(
            content=_html_page(
                "Lien invalide",
                "Lien invalide",
                "Ce lien d'annulation est introuvable ou a déjà expiré.",
                _PRIMARY,
            ),
            status_code=404,
        )

    if task.status in (TaskStatus.DONE, TaskStatus.MISSED):
        label = "terminée" if task.status == TaskStatus.DONE else "marquée comme manquée"
        return HTMLResponse(
            content=_html_page(
                "Action impossible",
                "Action impossible",
                f"La tâche « {task.title} » est déjà {label} et ne peut plus être annulée.",
                _PRIMARY,
            ),
            status_code=200,
        )

    if task.status == TaskStatus.CANCELLED:
        return HTMLResponse(
            content=_html_page(
                "Déjà annulée",
                "Tâche déjà annulée",
                f"La tâche « {task.title} » a déjà été annulée.",
                _GREY,
            ),
            status_code=200,
        )

    # Annulation effective
    task.status = TaskStatus.CANCELLED
    db.commit()

    cancel_task_jobs(task.id)

    return HTMLResponse(
        content=_html_page(
            "Tâche annulée",
            "Tâche annulée",
            f"Votre tâche « {task.title} » du {task.task_date.strftime('%d/%m/%Y')} "
            f"({task.start_time.strftime('%H:%M')} — {task.end_time.strftime('%H:%M')}) "
            "a bien été annulée.",
            _PRIMARY,
        ),
        status_code=200,
    )