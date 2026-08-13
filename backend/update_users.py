from app.database import SessionLocal
from app.models.schemas import User, SecurityGroup

def update_users():
    db = SessionLocal()
    try:
        default_group = db.query(SecurityGroup).filter_by(name="default").first()
        if not default_group:
            print("Default group not found!")
            return
            
        users = db.query(User).all()
        count = 0
        for user in users:
            has_default = any(g.name == "default" for g in user.security_groups)
            if not has_default:
                user.security_groups.append(default_group)
                count += 1
                
        if count > 0:
            db.commit()
            print(f"Added default group to {count} users.")
        else:
            print("All users already have the default group.")
    finally:
        db.close()

if __name__ == "__main__":
    update_users()
