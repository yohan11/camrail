# © MBIH NGALLY YOHAN JONATHAN & TIENTCHEU NLOM DAVID. Tous droits réservés.

import os
import sys

# Forcer le mode hors-ligne strict pour HuggingFace et Transformers au niveau système
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, SessionLocal
from app.models import schemas
from app.routers import auth, users, documents, search, assistant, dashboard
from app.security import hash_password
from app.seed import seed_database

# Initialize database tables directly if using SQLite for ease of development.
# For production/PostgreSQL, Alembic is used, but this is a useful fallback.
if settings.DATABASE_URL.startswith("sqlite"):
    schemas.Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialisation locale de l'application (100% hors-ligne, aucune requête sortante)
    yield

app = FastAPI(
    title="RailMind Lite API",
    description="Backend API for CAMRAIL RailMind Lite - RAG Engine (100% Local & Souverain)",
    version="1.0",
    lifespan=lifespan
)

# Middleware de durcissement des en-têtes HTTP de sécurité
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), geolocation=(), microphone=()"

    if getattr(settings, "ENABLE_HSTS", False):
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    # Cache-Control: no-store sur les réponses authentifiées
    is_authenticated = bool(
        request.headers.get("authorization")
        or request.cookies.get("access_token")
        or request.cookies.get("refresh_token")
        or getattr(request.state, "user", None)
    )
    if is_authenticated:
        response.headers["Cache-Control"] = "no-store"

    return response

# CORS configuration to connect the frontend easily
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(assistant.router)
app.include_router(dashboard.router)

# Also support /api/v1 prefix
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(assistant.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")

@app.on_event("startup")
def startup_event():
    import json
    import logging
    logger = logging.getLogger("railmind")

    db = SessionLocal()
    try:
        seed_database(db)

        # En production : désactiver impérativement les comptes de démonstration avec mots de passe par défaut
        if getattr(settings, "APP_ENV", "development") == "production":
            from app.security import verify_password
            from app.services.audit import log_audit_event
            demo_credentials = [
                ("admin@camrail.net", "adminpassword"),
                ("docadmin@camrail.net", "docadminpassword"),
                ("readonly@camrail.net", "readonlypassword"),
            ]
            for email, default_pwd in demo_credentials:
                demo_user = db.query(schemas.User).filter(schemas.User.email == email).first()
                if demo_user and verify_password(default_pwd, demo_user.password_hash):
                    if demo_user.is_active:
                        demo_user.is_active = False
                        db.commit()
                        logger.critical(
                            f"ALERTE CRITIQUE [demo_account_disabled] : Le compte de démonstration {email} utilisait encore son mot de passe par défaut en production. Il a été désactivé immédiatement."
                        )
                        log_audit_event(
                            db=db,
                            actor_user_id=None,
                            action="demo_account_disabled",
                            entity_type="user",
                            entity_id=str(demo_user.id),
                            details={"email": email, "reason": "default_password_in_production"}
                        )
    finally:
        db.close()

    # Verification de la calibration RAG_MIN_CONFIDENCE pour EMBEDDING_MODEL
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    calib_candidates = [
        os.path.join(backend_dir, "eval_results", "calibration.json"),
        os.path.join(backend_dir, "..", "eval_results", "calibration.json"),
    ]
    calib_found = False
    calib_model = None
    for cp in calib_candidates:
        if os.path.exists(cp):
            try:
                with open(cp, "r", encoding="utf-8") as f:
                    cdata = json.load(f)
                    calib_model = cdata.get("embedding_model")
                    calib_found = True
                    break
            except Exception:
                pass

    if not calib_found or calib_model != settings.EMBEDDING_MODEL:
        print("\n" + "!" * 80)
        print(f"[AVERTISSEMENT CALIBRATION] Le seuil RAG_MIN_CONFIDENCE={settings.RAG_MIN_CONFIDENCE} n'a pas ete calibre pour le modele actuel '{settings.EMBEDDING_MODEL}' (calibre pour : '{calib_model}').")
        print("Veuillez executer : python scripts/calibrate_threshold.py pour recalibrer le seuil.")
        print("!" * 80 + "\n")
        logger.warning(f"RAG_MIN_CONFIDENCE non calibre pour {settings.EMBEDDING_MODEL}. Lancez scripts/calibrate_threshold.py.")


@app.get("/")
def read_root():
    return {
        "message": "Welcome to the RailMind Lite API (100% Local)",
        "status": "online",
        "documentation": "/docs"
    }


@app.get("/health")
@app.get("/api/v1/health")
def health_check():
    """
    Vérification de l'état de santé du système sans authentification :
    - Connexion à la base de données PostgreSQL
    - Disponibilité du serveur local Ollama
    - Présence du modèle d'embedding dans MODELS_DIR
    Renvoie un code HTTP 200 si tout est opérationnel, 503 si un composant fait défaut.
    """
    import httpx
    from sqlalchemy import text
    from fastapi.responses import JSONResponse

    health_status = {
        "status": "healthy",
        "database": "ok",
        "ollama": "ok",
        "embedding_model": "ok"
    }
    is_healthy = True

    # 1. Base de données
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        health_status["database"] = f"error: {str(e)}"
        is_healthy = False

    # 2. Moteur LLM Ollama local
    try:
        with httpx.Client(timeout=3.0) as client:
            r = client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if r.status_code != 200:
                health_status["ollama"] = f"http_{r.status_code}"
                is_healthy = False
    except Exception as e:
        health_status["ollama"] = f"error: {str(e)}"
        is_healthy = False

    # 3. Modèle d'embedding local dans MODELS_DIR
    models_dir = getattr(settings, "MODELS_DIR", "./models")
    if not os.path.isabs(models_dir):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        models_dir = os.path.abspath(os.path.join(base_dir, models_dir))
    model_name = getattr(settings, "EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
    model_basename = model_name.split("/")[-1]
    
    candidate_paths = [
        os.path.join(models_dir, model_basename),
        os.path.join(models_dir, model_name),
        os.path.join(models_dir, model_name.replace("/", "_")),
        models_dir
    ]
    model_found = any(
        os.path.isdir(p) and (os.path.exists(os.path.join(p, "config.json")) or os.path.exists(os.path.join(p, "modules.json")))
        for p in candidate_paths
    )
    if not model_found:
        health_status["embedding_model"] = "missing_files"
        is_healthy = False

    if not is_healthy:
        health_status["status"] = "unhealthy"
        return JSONResponse(status_code=503, content=health_status)

    return health_status
