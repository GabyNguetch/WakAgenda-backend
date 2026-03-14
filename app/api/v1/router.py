"""
app/api/v1/router.py  ← FICHIER MODIFIÉ
Agrège tous les routers de l'API v1.

AJOUTS PAR RAPPORT À LA VERSION ORIGINALE (marqués ← NEW) :
  - reports_weekly       → GET  /api/v1/reports/weekly-schedule
  - reports_tf_docx      → GET  /api/v1/reports/technico-fonctionnel-docx
  - export_import        → GET  /api/v1/export/csv
                         → POST /api/v1/import/csv
  - broadcast            → POST /api/v1/notifications/broadcast
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    reports_tf,
    users,
    tasks,
    notifications,
    reports,
    domains,
    task_actions,
    task_comments,
    # ── Nouveaux modules ───────────────────────────────────────────────────────
    reports_weekly,      # ← NEW  Emploi du temps hebdomadaire PDF
    reports_tf_docx,     # ← NEW  Rapport technico-fonctionnel DOCX
    export_import,       # ← NEW  Export/Import CSV
    broadcast,           # ← NEW  Broadcast email
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(users.router)
# task_actions AVANT tasks pour éviter la capture de /tasks/action/... par /{task_id}
api_router.include_router(task_actions.router)
api_router.include_router(tasks.router)
api_router.include_router(notifications.router)
api_router.include_router(reports.router)
api_router.include_router(domains.router)
api_router.include_router(task_comments.router)
api_router.include_router(reports_tf.router)

# ── Nouveaux routers ───────────────────────────────────────────────────────────
api_router.include_router(reports_weekly.router)   # ← NEW
api_router.include_router(reports_tf_docx.router)  # ← NEW
api_router.include_router(export_import.router)    # ← NEW  (pas de prefix, routes /export et /import)
api_router.include_router(broadcast.router)        # ← NEW