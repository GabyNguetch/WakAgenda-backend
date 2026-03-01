"""
app/main.py
Point d'entrée principal de WakAgenda Backend.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.api.v1.router import api_router

# 1. Définir le chemin globalement pour éviter la NameError
UPLOADS_PATH = Path(settings.UPLOAD_DIR)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "API backend de WakAgenda – Agenda interactif des stagiaires.\n\n"
        "Développé pour la DSI de Boissons du Cameroun (SABC).\n\n"
        "**Authentification** : Bearer JWT. Utilisez `/api/v1/auth/login`."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    license_info={"name": "Usage interne SABC"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

# 2. Utiliser la variable globale UPLOADS_PATH ici
# On s'assure que le dossier existe dès le chargement pour éviter une erreur de StaticFiles
UPLOADS_PATH.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_PATH)), name="uploads")


@app.get("/health", tags=["Health"], summary="État du serveur")
def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.on_event("startup")
async def on_startup():
    """Démarre le scheduler et initialise les données de base en mode DEBUG."""
    uploads_dir = Path(settings.UPLOAD_DIR)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    # Scheduler APScheduler
    from app.services.scheduler_service import start_scheduler
    start_scheduler()

    if settings.DEBUG:
        from app.db.session import engine, SessionLocal
        from app.db.base_class import Base
        import app.models.user          # noqa
        import app.models.task          # noqa
        import app.models.notification  # noqa
        import app.models.domain        # noqa
        import app.models.task_comment  # noqa

        Base.metadata.create_all(bind=engine)

        # ── Seed des domaines système ─────────────────────────────────────────
        _seed_system_domains()

        print(f"✅  {settings.APP_NAME} v{settings.APP_VERSION} démarré en mode DEBUG.")
        print(f"📄  Swagger : http://127.0.0.1:8000/docs")
        print(f"⏰  Scheduler APScheduler démarré.")


def _seed_system_domains() -> None:
    """
    Insère les domaines système par défaut s'ils n'existent pas encore.
    Appelé uniquement au démarrage en mode DEBUG.
    """
    from app.db.session import SessionLocal
    from app.repositories.domain_repository import DomainRepository

    SYSTEM_DOMAINS = ["Technique", "Administratif", "Commercial", "Transversal"]

    db = SessionLocal()
    try:
        repo = DomainRepository(db)
        for name in SYSTEM_DOMAINS:
            if not repo.name_exists(name):
                repo.create(name=name, is_system=True)
                print(f"  ↳ Domaine système créé : {name}")
    finally:
        db.close()


@app.on_event("shutdown")
async def on_shutdown():
    from app.services.scheduler_service import shutdown_scheduler
    shutdown_scheduler()