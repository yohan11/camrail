# Â© 2026 MBIH NGALLY YOHAN JONATHAN & TIENTCHEU NLOM DAVID. Tous droits rÃ©servÃ©s.
# Utilisation en production strictement interdite sans licence commerciale.

import os
import sys
import httpx
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.services.connectivity import is_online
# CRITICAL: We must set HF_HUB_OFFLINE before ANY file imports sentence_transformers
if not is_online(timeout_seconds=2.0):
    os.environ["HF_HUB_OFFLINE"] = "1"

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

# 1. METS TON URL ICI (Assure-toi de retirer le long hash de commit juste aprÃ¨s /raw/)
# Exemple: https://gist.githubusercontent.com/yohan11/123456789/raw/railmind_licence.json
BASE_LICENCE_URL = "https://gist.githubusercontent.com/yohan11/a91b688220a6c9d582a789331ed25303/raw/railmind_licence.json"

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("VÃ©rification de la licence RailMind Lite...")
    try:
        # 2. CACHE BUSTING : On ajoute l'heure exacte Ã  l'URL pour contourner le cache de GitHub
        url_sans_cache = f"{BASE_LICENCE_URL}?t={time.time()}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url_sans_cache, timeout=5.0)
            data = response.json()
            
            # Si le statut n'est pas "active", on bloque tout
            if data.get("status") != "active":
                print("ERREUR CRITIQUE : Licence rÃ©voquÃ©e ou invalide. Contactez les dÃ©veloppeurs.")
                sys.exit(1)
            else:
                print("Licence VALIDE. DÃ©marrage de l'application...")
    except Exception as e:
        print(f"INFO : Impossible de contacter le serveur de licence distant ({e}). Démarrage en mode hors-ligne.")
    
    yield

app = FastAPI(
    title="RailMind Lite API",
    description="Backend API for CAMRAIL RailMind Lite - RAG Engine",
    version="1.0",
    lifespan=lifespan
)

# CORS configuration to connect the frontend easily
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
    # Seed initial users and groups if they don't exist
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()

@app.get("/")
def read_root():
    return {
        "message": "Welcome to the RailMind Lite API",
        "status": "online",
        "documentation": "/docs"
    }

