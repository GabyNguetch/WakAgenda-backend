"""
app/api/v1/router.py
Agrège tous les routers de l'API v1.
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
# router.py
api_router.include_router(reports_tf.router)  # ← plus de prefix ici