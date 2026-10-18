import math
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from authlib.integrations.starlette_client import OAuth
import jwt

from app.database import get_db
from app.models.schemas import User, RefreshToken, RevokedToken, LoginAttempt
from app.schemas.auth import Token
from app.security import (
    verify_password,
    create_access_token,
    verify_token,
    create_refresh_token,
    hash_refresh_token,
    DUMMY_BCRYPT_HASH,
)
from app.services.audit import log_audit_event
from app.config import settings

logger = logging.getLogger("railmind")

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
    logger.info(
        "SSO Microsoft désactivé : variables MICROSOFT_CLIENT_ID / MICROSOFT_CLIENT_SECRET non configurées."
    )


def get_client_ip(request: Request) -> str:
    """
    Extrait l'adresse IP du client de manière sécurisée.
    Utilise request.client.host par défaut. N'utilise le premier en-tête X-Forwarded-For
    QUE si la requête provient d'un reverse proxy de confiance listé dans TRUSTED_PROXIES.
    """
    client_host = request.client.host if request.client else "127.0.0.1"
    trusted_proxies = settings.trusted_proxies_list
    if trusted_proxies and client_host in trusted_proxies:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            ips = [ip.strip() for ip in forwarded_for.split(",") if ip.strip()]
            if ips:
                return ips[0]
    return client_host


def ensure_utc(dt: Optional[datetime]) -> datetime:
    """Garantit qu'un datetime est conscient du fuseau horaire (offset-aware UTC)."""
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_cookie_path(request: Request) -> str:
    """Détermine le chemin du cookie selon le préfixe utilisé (/api/v1/auth ou /auth)."""
    return "/api/v1/auth" if request.url.path.startswith("/api/v1") else "/auth"


def set_refresh_cookie(response: Response, raw_token: str, path: str):
    response.set_cookie(
        key="refresh_token",
        value=raw_token,
        httponly=True,
        samesite="strict",
        secure=(settings.APP_ENV == "production"),
        max_age=settings.REFRESH_TOKEN_EXPIRE_HOURS * 3600,
        path=path
    )


def clear_refresh_cookie(response: Response, path: str):
    response.delete_cookie(key="refresh_token", path=path)
    # Effacement défensif sur les chemins alternatifs usuels
    response.delete_cookie(key="refresh_token", path="/auth")
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")
    response.delete_cookie(key="refresh_token", path="/")


@router.get("/login/microsoft")
async def login_microsoft(request: Request):
    if not (settings.MICROSOFT_CLIENT_ID and settings.MICROSOFT_CLIENT_SECRET):
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
    raw_refresh, token_hash = create_refresh_token()
    now = datetime.now(timezone.utc)
    refresh_expires = now + timedelta(hours=settings.REFRESH_TOKEN_EXPIRE_HOURS)
    
    client_ip = get_client_ip(request)
    db_refresh = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        created_at=now,
        expires_at=refresh_expires,
        user_agent=request.headers.get("user-agent"),
        ip=client_ip
    )
    db.add(db_refresh)
    db.commit()
    
    log_audit_event(
        db=db, actor_user_id=user.id, action="login_success_sso",
        entity_type="user", entity_id=str(user.id), details={"email": user.email, "ip": client_ip}
    )
    
    response = RedirectResponse(url=f"{settings.FRONTEND_URL.rstrip('/')}/assistant")
    cookie_path = get_cookie_path(request)
    set_refresh_cookie(response, raw_refresh, cookie_path)
    return response


@router.post("/login", response_model=Token)
def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    now = datetime.now(timezone.utc)
    client_ip = get_client_ip(request)
    email_lower = form_data.username.strip().lower()
    window_start = now - timedelta(minutes=settings.LOCKOUT_MINUTES)

    # 1. Protection Brute-Force par IP (20 tentatives en 15 min)
    ip_attempts_count = db.query(LoginAttempt).filter(
        LoginAttempt.ip == client_ip,
        LoginAttempt.attempted_at >= window_start
    ).count()

    if ip_attempts_count >= settings.LOGIN_MAX_PER_IP:
        oldest_in_window = db.query(LoginAttempt).filter(
            LoginAttempt.ip == client_ip,
            LoginAttempt.attempted_at >= window_start
        ).order_by(LoginAttempt.attempted_at.asc()).first()
        
        wait_seconds = int(math.ceil(
            (ensure_utc(oldest_in_window.attempted_at) + timedelta(minutes=settings.LOCKOUT_MINUTES) - now).total_seconds()
        ))
        wait_seconds = max(1, wait_seconds)
        wait_minutes = max(1, int(math.ceil(wait_seconds / 60.0)))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Trop de tentatives, réessayez dans {wait_minutes} minutes",
            headers={"Retry-After": str(wait_seconds)}
        )

    # 2. Protection Brute-Force par Compte (5 échecs consécutifs en 15 min)
    recent_attempts = db.query(LoginAttempt).filter(
        LoginAttempt.email_lower == email_lower,
        LoginAttempt.attempted_at >= window_start
    ).order_by(LoginAttempt.attempted_at.desc()).all()

    consecutive_failures = 0
    latest_failure_time = None
    for att in recent_attempts:
        if not att.success:
            consecutive_failures += 1
            if latest_failure_time is None:
                latest_failure_time = att.attempted_at
        else:
            break

    if consecutive_failures >= settings.LOGIN_MAX_FAILURES and latest_failure_time:
        wait_seconds = int(math.ceil(
            (ensure_utc(latest_failure_time) + timedelta(minutes=settings.LOCKOUT_MINUTES) - now).total_seconds()
        ))
        if wait_seconds > 0:
            wait_minutes = max(1, int(math.ceil(wait_seconds / 60.0)))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Trop de tentatives, réessayez dans {wait_minutes} minutes",
                headers={"Retry-After": str(wait_seconds)}
            )

    # 3. Authentification et Atténuation des Attaques par Analyse Temporelle (timing attacks)
    user = db.query(User).filter(User.email == email_lower).first()
    
    if not user:
        # Utilisateur inexistant : calcul bcrypt factice pour temps de réponse identique
        verify_password(form_data.password, DUMMY_BCRYPT_HASH)
        
        # Enregistrement de l'échec
        attempt = LoginAttempt(email_lower=email_lower, ip=client_ip, attempted_at=now, success=False)
        db.add(attempt)
        db.commit()
        
        log_audit_event(
            db=db,
            actor_user_id=None,
            action="login_failure",
            entity_type="user",
            entity_id="unknown",
            details={"email_lower": email_lower, "ip": client_ip}
        )
        
        # Vérification si cet échec atteint le seuil de verrouillage
        if consecutive_failures + 1 >= settings.LOGIN_MAX_FAILURES:
            log_audit_event(
                db=db,
                actor_user_id=None,
                action="account_locked",
                entity_type="user",
                entity_id="unknown",
                details={"email_lower": email_lower, "ip": client_ip, "lockout_minutes": settings.LOCKOUT_MINUTES}
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Utilisateur existant : vérification mot de passe et statut actif
    password_ok = verify_password(form_data.password, user.password_hash)
    if not password_ok or not user.is_active:
        attempt = LoginAttempt(email_lower=email_lower, ip=client_ip, attempted_at=now, success=False)
        db.add(attempt)
        db.commit()
        
        log_audit_event(
            db=db,
            actor_user_id=user.id,
            action="login_failure",
            entity_type="user",
            entity_id=str(user.id),
            details={"email_lower": email_lower, "ip": client_ip, "is_active": user.is_active}
        )

        if consecutive_failures + 1 >= settings.LOGIN_MAX_FAILURES:
            log_audit_event(
                db=db,
                actor_user_id=user.id,
                action="account_locked",
                entity_type="user",
                entity_id=str(user.id),
                details={"email_lower": email_lower, "ip": client_ip, "lockout_minutes": settings.LOCKOUT_MINUTES}
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4. Connexion Réussie
    attempt = LoginAttempt(email_lower=email_lower, ip=client_ip, attempted_at=now, success=True)
    db.add(attempt)

    access_token = create_access_token(subject=user.email, role=user.role)
    raw_refresh, token_hash = create_refresh_token()
    refresh_expires = now + timedelta(hours=settings.REFRESH_TOKEN_EXPIRE_HOURS)

    db_refresh = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        created_at=now,
        expires_at=refresh_expires,
        user_agent=request.headers.get("user-agent"),
        ip=client_ip
    )
    db.add(db_refresh)
    db.commit()

    log_audit_event(
        db=db,
        actor_user_id=user.id,
        action="login_success",
        entity_type="user",
        entity_id=str(user.id),
        details={"email": user.email, "ip": client_ip}
    )

    cookie_path = get_cookie_path(request)
    set_refresh_cookie(response, raw_refresh, cookie_path)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role
    }


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    raw_token = request.cookies.get("refresh_token")
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token_hash = hash_refresh_token(raw_token)
    db_token = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    cookie_path = get_cookie_path(request)

    if not db_token:
        clear_refresh_cookie(response, cookie_path)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    now = datetime.now(timezone.utc)

    # Détection de réutilisation (Jeton déjà révoqué)
    if db_token.revoked_at is not None:
        user_id = db_token.user_id
        # ALERTE SÉCURITÉ : révoque TOUS les refresh tokens de cet utilisateur immédiatement
        db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None)
        ).update({"revoked_at": now})
        db.commit()

        log_audit_event(
            db=db,
            actor_user_id=user_id,
            action="refresh_reuse_detected",
            entity_type="refresh_token",
            entity_id=str(db_token.id),
            details={
                "user_id": user_id,
                "token_id": db_token.id,
                "ip": get_client_ip(request),
                "severity": "CRITICAL"
            }
        )

        clear_refresh_cookie(response, cookie_path)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session compromised: refresh token reuse detected"
        )

    # Vérification d'expiration
    token_exp = db_token.expires_at
    if token_exp.tzinfo is None:
        token_exp = token_exp.replace(tzinfo=timezone.utc)

    if token_exp < now:
        clear_refresh_cookie(response, cookie_path)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    user = db.query(User).filter(User.id == db_token.user_id).first()
    if not user or not user.is_active:
        clear_refresh_cookie(response, cookie_path)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    # Rotation systématique du refresh token
    new_access_token = create_access_token(subject=user.email, role=user.role)
    new_raw_refresh, new_token_hash = create_refresh_token()
    new_refresh_expires = now + timedelta(hours=settings.REFRESH_TOKEN_EXPIRE_HOURS)

    client_ip = get_client_ip(request)
    new_db_token = RefreshToken(
        user_id=user.id,
        token_hash=new_token_hash,
        created_at=now,
        expires_at=new_refresh_expires,
        user_agent=request.headers.get("user-agent"),
        ip=client_ip
    )
    db.add(new_db_token)
    db.flush()

    # Révocation de l'ancien jeton et liaison avec le nouveau
    db_token.revoked_at = now
    db_token.replaced_by = new_db_token.id
    db.commit()

    set_refresh_cookie(response, new_raw_refresh, cookie_path)

    return {
        "access_token": new_access_token,
        "role": user.role,
        "email": user.email
    }


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    actor_id = None
    client_ip = get_client_ip(request)

    # 1. Révocation de l'access token via jti dans revoked_tokens
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token_str = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(
                token_str,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_exp": False, "verify_aud": False, "verify_iss": False}
            )
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti and exp:
                exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
                existing = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
                if not existing:
                    db.add(RevokedToken(jti=jti, expires_at=exp_dt, created_at=now))
        except Exception as e:
            logger.debug(f"Impossible de décoder l'access token au logout : {e}")

    # 2. Révocation du refresh token courant en base
    raw_refresh = request.cookies.get("refresh_token")
    if raw_refresh:
        token_hash = hash_refresh_token(raw_refresh)
        db_refresh = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
        if db_refresh:
            actor_id = db_refresh.user_id
            if db_refresh.revoked_at is None:
                db_refresh.revoked_at = now

    # 3. Purge des lignes expirées pour éviter l'enflure
    try:
        db.query(RevokedToken).filter(RevokedToken.expires_at < now).delete(synchronize_session=False)
        db.query(RefreshToken).filter(RefreshToken.expires_at < now).delete(synchronize_session=False)
    except Exception as e:
        logger.warning(f"Erreur lors de la purge des jetons expirés : {e}")

    db.commit()

    # 4. Suppression des cookies de refresh
    cookie_path = get_cookie_path(request)
    clear_refresh_cookie(response, cookie_path)

    # 5. Journalisation de l'audit
    log_audit_event(
        db=db,
        actor_user_id=actor_id,
        action="logout",
        entity_type="auth",
        entity_id=str(actor_id) if actor_id else "unknown",
        details={"ip": client_ip}
    )

    return {"detail": "Déconnexion réussie"}
