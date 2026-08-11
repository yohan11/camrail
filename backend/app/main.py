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

app = FastAPI(
    title="RailMind Lite API",
    description="Backend API for CAMRAIL RailMind Lite - RAG Engine",
    version="1.0"
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
