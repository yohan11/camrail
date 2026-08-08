from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import json
from app.database import get_db
from app.models.schemas import User, AuditEvent
from app.schemas.auth import Token
from app.security import verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
        
    # Generate token
    access_token = create_access_token(subject=user.email, role=user.role)
    
    # Create audit event
    audit_event = AuditEvent(
        actor_user_id=user.id,
        action="login",
        entity_type="users",
        entity_id=str(user.id),
        details_json=json.dumps({"email": user.email, "success": True})
    )
    db.add(audit_event)
    db.commit()
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role
    }
