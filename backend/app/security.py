from datetime import datetime, timedelta, timezone
from typing import Any, Union, Dict, Optional
import jwt
import bcrypt
from app.config import settings
from app.models.schemas import User, UserRole
from typing import Tuple, Optional, List

def get_effective_search_scope(user: User) -> Tuple[Optional[str], Optional[List[str]]]:
    """
    Returns (department, security_groups) based on the user's role.
    - Admins see all departments and all security groups.
    - Read-only users are restricted to their department (if set) and their assigned security groups.
    """
    department = user.department if user.role == UserRole.READ_ONLY else None
    
    if user.role in [UserRole.ADMIN, UserRole.DOCUMENT_ADMIN]:
        security_groups = None
    else:
        security_groups = [group.name for group in user.security_groups]
        
    return department, security_groups

def can_access_document(user: User, doc: Optional[Any]) -> bool:
    """
    Règle unique d'accès à un document.
    S'appuie sur get_effective_search_scope et reproduit fidèlement
    les filtres de hybrid_search :
    - Admins et Document Admins ont un accès total.
    - Pour les utilisateurs read_only :
      1. Statut actif uniquement (doc.status == 'active').
      2. Si scope_department est défini (user.department), doc.department doit correspondre exactement.
      3. Si user_security_groups est défini :
         - Si la liste est vide, aucun accès n'est accordé.
         - Le document doit posséder au moins un groupe de sécurité en commun avec l'utilisateur.
    """
    if doc is None:
        return False

    if user.role in [UserRole.ADMIN, UserRole.DOCUMENT_ADMIN]:
        return True

    # 1. Statut actif
    if doc.status != "active":
        return False

    # 2. Périmètre effectif (département & groupes de sécurité)
    scope_department, user_security_groups = get_effective_search_scope(user)

    if scope_department and doc.department != scope_department:
        return False

    if user_security_groups is not None:
        if not user_security_groups:
            return False
        doc_group_names = [g.name for g in doc.security_groups]
        if not any(g in user_security_groups for g in doc_group_names):
            return False

    return True

def ensure_document_access(user: User, doc: Optional[Any], db: Any, action: str = "read") -> Any:
    """
    Vérifie l'accès d'un utilisateur à un document.
    Si l'accès est refusé ou le document introuvable, écrit un événement d'audit 'access_denied'
    puis lève une HTTPException 404 "Document non trouvé" (et non 403, pour ne pas révéler l'existence).
    """
    from fastapi import HTTPException, status
    from app.services.audit import log_audit_event
    
    if doc is None or not can_access_document(user, doc):
        motif = "not_found" if doc is None else ("inactive" if getattr(doc, "status", None) != "active" else "restricted_scope")
        log_audit_event(
            db=db,
            actor_user_id=user.id if user else None,
            action="access_denied",
            entity_type="document",
            entity_id=str(doc.id) if doc else "unknown",
            details={"action": action, "motif": motif, "reason": motif}
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document non trouvé"
        )
    return doc

def filter_accessible_documents(query: Any, user: User) -> Any:
    """
    Filtre une requête SQLAlchemy Document selon la règle d'accès unique.
    Utilisé pour list_documents et le dashboard afin d'éviter toute réécriture manuelle.
    """
    if user.role in [UserRole.ADMIN, UserRole.DOCUMENT_ADMIN]:
        return query

    from app.models.schemas import Document, SecurityGroup
    query = query.filter(Document.status == "active")
    
    scope_department, user_security_groups = get_effective_search_scope(user)
    if scope_department:
        query = query.filter(Document.department == scope_department)
        
    if user_security_groups is not None:
        if not user_security_groups:
            return query.filter(Document.id == -1)
        query = query.filter(Document.security_groups.any(SecurityGroup.name.in_(user_security_groups)))
        
    return query

def ensure_conversation_access(user: User, conv: Optional[Any], db: Any, action: str = "read") -> Any:
    """
    Vérifie la propriété d'une conversation.
    Une conversation n'est lisible, modifiable ou supprimable que par son propriétaire.
    """
    from fastapi import HTTPException, status
    from app.services.audit import log_audit_event
    
    if conv is None or conv.user_id != user.id:
        log_audit_event(
            db=db,
            actor_user_id=user.id if user else None,
            action="access_denied",
            entity_type="conversation",
            entity_id=str(conv.id) if conv else "unknown",
            details={"action": action}
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation non trouvée"
        )
    return conv

import uuid
import secrets
import hashlib

DUMMY_BCRYPT_HASH = "$2b$12$e8uq.7E13o7kY7UuFh0w9OHxN5PzF6Nq84h7V7FvUqjRjJz.q5e.a"

def hash_password(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def create_access_token(subject: Union[str, Any], role: str, expires_delta: Union[timedelta, None] = None) -> str:
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    jti = str(uuid.uuid4())
    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": now,
        "jti": jti,
        "iss": "railmind",
        "aud": "railmind-api",
        "type": "access",
        "role": role  # Le rôle écrit dans le jeton est IGNORÉ côté serveur
    }
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def verify_token(token: str, db: Optional[Any] = None) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            issuer="railmind",
            audience="railmind-api"
        )
        if payload.get("type") != "access":
            return None
            
        jti = payload.get("jti")
        if not jti:
            return None
            
        if db is not None:
            from app.models.schemas import RevokedToken
            revoked = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
            if revoked:
                return None
                
        return payload
    except jwt.PyJWTError:
        return None

def create_refresh_token() -> Tuple[str, str]:
    """Génère un jeton de renouvellement aléatoire de 256 bits et son hash SHA-256."""
    raw_token = secrets.token_urlsafe(32)  # 32 octets = 256 bits
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    return raw_token, token_hash

def hash_refresh_token(raw_token: str) -> str:
    """Calcule le hash SHA-256 d'un jeton de renouvellement brut."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

