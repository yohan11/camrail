from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import json
from app.database import get_db
from app.models.schemas import User
from app.schemas.auth import Token
from app.security import verify_password, create_access_token, verify_token
from app.services.audit import log_audit_event
from app.config import settings

from authlib.integrations.starlette_client import OAuth
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth = OAuth()
if settings.MICROSOFT_CLIENT_ID and settings.MICROSOFT_CLIENT_SECRET:
    oauth.register(
        name='microsoft',
        client_id=settings.MICROSOFT_CLIENT_ID,
        client_secret=settings.MICROSOFT_CLIENT_SECRET,
        server_metadata_url=f'https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}/v2.0/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )
else:
    import logging
    logging.getLogger("railmind").info(
        "SSO Microsoft désactivé : variables MICROSOFT_CLIENT_ID / MICROSOFT_CLIENT_SECRET non configurées."
    )

@router.get("/login/microsoft")
async def login_microsoft(request: Request):
    if not (settings.MICROSOFT_CLIENT_ID and settings.MICROSOFT_CLIENT_SECRET):
        import logging
        logger = logging.getLogger("railmind")
        if getattr(settings, "APP_ENV", "development") == "development":
            logger.warning(
                "SSO Microsoft non configuré : redirection mock_sso active uniquement en mode développement."
            )
            return RedirectResponse(url=f"{settings.FRONTEND_URL.rstrip('/')}/assistant?mock_sso=true")
        else:
            logger.warning(
                "Tentative de connexion SSO Microsoft alors que le service n'est pas configuré en production."
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="L'authentification SSO Microsoft n'est pas configurée sur cette instance."
            )
    
    api_base = settings.API_PUBLIC_URL.rstrip('/')
    redirect_uri = f"{api_base}/api/v1/auth/callback/microsoft"
    return await oauth.microsoft.authorize_redirect(request, redirect_uri)

@router.get("/callback/microsoft")
async def auth_microsoft_callback(request: Request, db: Session = Depends(get_db)):
    if not (settings.MICROSOFT_CLIENT_ID and settings.MICROSOFT_CLIENT_SECRET):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SSO Microsoft non configuré"
        )
        
    try:
        token = await oauth.microsoft.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"SSO Error: {str(e)}")
        
    user_info = token.get('userinfo')
    if not user_info:
        raise HTTPException(status_code=400, detail="SSO Error: User info not returned")
        
    email = user_info.get("email") or user_info.get("preferred_username")
    name = user_info.get("name")
    
    if not email:
        raise HTTPException(status_code=400, detail="SSO Error: No email provided by provider")
        
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        # Auto-provision user
        user = User(
            email=email,
            password_hash="sso_managed",
            full_name=name,
            role="read_only",
            department="Général",
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        log_audit_event(
            db=db, actor_user_id=user.id, action="user_provisioned_sso",
            entity_type="user", entity_id=str(user.id), details={"email": email}
        )
        
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
        
    access_token = create_access_token(subject=user.email, role=user.role)
    
    log_audit_event(
        db=db, actor_user_id=user.id, action="login_success_sso",
        entity_type="user", entity_id=str(user.id), details={"email": user.email}
    )
    
    # Redirection vers l'URL publique configurée du frontend
    response = RedirectResponse(url=f"{settings.FRONTEND_URL.rstrip('/')}/assistant")
    response.set_cookie(
        key="refresh_token", 
        value=access_token, 
        httponly=True, 
        samesite="lax",
        max_age=1440 * 60
    )
    return response

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
