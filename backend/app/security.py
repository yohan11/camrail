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
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject), "role": role}
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.PyJWTError:
        return None
