from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import json
from app.database import get_db
from app.models.schemas import User
from app.schemas.auth import Token
from app.security import verify_password, create_access_token, verify_token
from app.services.audit import log_audit_event

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=Token)
def login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        log_audit_event(
            db=db,
            actor_user_id=None,
            action="login_failed",
            entity_type="user",
            entity_id="unknown" if not user else str(user.id),
            details={"attempted_email": form_data.username}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        log_audit_event(
            db=db,
            actor_user_id=user.id,
            action="login_failed",
            entity_type="user",
            entity_id=str(user.id),
            details={"attempted_email": form_data.username, "reason": "inactive"}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
        
    # Generate token
    access_token = create_access_token(subject=user.email, role=user.role)
    
    # Create audit event
    log_audit_event(
        db=db,
        actor_user_id=user.id,
        action="login_success",
        entity_type="user",
        entity_id=str(user.id),
        details={"email": user.email}
    )
    
    # Set the refresh_token cookie
    response.set_cookie(
        key="refresh_token", 
        value=access_token, 
        httponly=True, 
        samesite="lax",
        max_age=1440 * 60
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role
    }

@router.post("/refresh")
def refresh(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        
    user = db.query(User).filter(User.email == payload.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
        
    new_token = create_access_token(subject=user.email, role=user.role)
    
    return {
        "access_token": new_token,
        "role": user.role,
        "email": user.email
    }
