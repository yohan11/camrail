# © 2026 MBIH NGALLY YOHAN JONATHAN & TIENTCHEU NLOM DAVID. Tous droits réservés.

import os
import sys

# Forcer le mode hors-ligne strict pour HuggingFace et Transformers au niveau système
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from contextlib import asynccontextmanager
from fastapi import FastAPI
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

    # Seed initial users and groups if they don't exist
    db = SessionLocal()
    try:
        seed_database(db)
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
