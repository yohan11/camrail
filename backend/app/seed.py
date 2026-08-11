from sqlalchemy.orm import Session
from app.models import schemas
from app.security import hash_password

def seed_database(db: Session):
    """
    Seeds the database with initial security groups and users if they don't exist.
    """
    try:
        user_count = db.query(schemas.User).count()
        group_count = db.query(schemas.SecurityGroup).count()
        
        if group_count == 0:
            print("No security groups found. Seeding initial groups...")
            for g_name in ["default", "operations", "safety"]:
                db.add(schemas.SecurityGroup(name=g_name, description=f"{g_name.capitalize()} Group"))
            db.commit()

        if user_count == 0:
            print("No users found. Seeding initial manager accounts...")
            
            # Roles: admin, document_admin, read_only
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
                    "role": "document_admin"
                },
                {
                    "email": "readonly@camrail.net",
                    "password": "readonlypassword",
                    "full_name": "Read-Only User",
                    "role": "read_only",
                    "department": "Formation"
                }
            ]
            
            for user_data in initial_users:
                hashed_pwd = hash_password(user_data["password"])
                db_user = schemas.User(
                    email=user_data["email"],
                    password_hash=hashed_pwd,
                    full_name=user_data["full_name"],
                    role=user_data["role"],
                    department=user_data.get("department"),
                    is_active=True
                )
                db.add(db_user)
            
            db.commit()
            print("Seed completed successfully!")
        else:
            print("Database already seeded with users and groups.")
    except Exception as e:
        print(f"Error during seeding: {e}")
        db.rollback()
