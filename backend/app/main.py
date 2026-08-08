from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, SessionLocal
from app.models import schemas
from app.routers import auth, users
from app.security import hash_password

# Initialize database tables directly if using SQLite for ease of development.
# For production/PostgreSQL, Alembic is used, but this is a useful fallback.
if settings.DATABASE_URL.startswith("sqlite"):
    schemas.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="RailMind Lite API",
    description="Backend API for CAMRAIL RailMind Lite - RAG & Workforce Rostering",
    version="1.0"
)

# CORS configuration to connect the frontend easily
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for local dev connection
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)

@app.on_event("startup")
def startup_event():
    # Seed initial users if they don't exist
    db = SessionLocal()
    try:
        user_count = db.query(schemas.User).count()
        if user_count == 0:
            print("No users found. Seeding initial manager accounts...")
            
            # Roles: admin, document_administrator, roster_manager, read_only_manager
            initial_users = [
                {
                    "email": "admin@camrail.net",
                    "password": "adminpassword",
                    "full_name": "System Admin",
                    "role": "admin"
                },
                {
                    "email": "docadmin@camrail.net",
                    "password": "docadminpassword",
                    "full_name": "Document Admin",
                    "role": "document_administrator"
                },
                {
                    "email": "roster@camrail.net",
                    "password": "rosterpassword",
                    "full_name": "Roster Manager",
                    "role": "roster_manager"
                },
                {
                    "email": "readonly@camrail.net",
                    "password": "readonlypassword",
                    "full_name": "Read-Only Manager",
                    "role": "read_only_manager"
                }
            ]
            
            for user_data in initial_users:
                hashed_pwd = hash_password(user_data["password"])
                db_user = schemas.User(
                    email=user_data["email"],
                    password_hash=hashed_pwd,
                    full_name=user_data["full_name"],
                    role=user_data["role"],
                    is_active=True
                )
                db.add(db_user)
            
            db.commit()
            print("Seed completed successfully!")
    except Exception as e:
        print(f"Error during startup seeding: {e}")
    finally:
        db.close()

@app.get("/")
def read_root():
    return {
        "message": "Welcome to the RailMind Lite API",
        "status": "online",
        "documentation": "/docs"
    }
