from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from app.database import get_db
from app.models.schemas import User, LoginAttempt, SecurityGroup
from app.schemas.user import UserResponse, UserCreate, UserUpdate
from app.deps import get_current_user, RoleChecker
from app.security import hash_password
from app.services.audit import log_audit_event

router = APIRouter(prefix="/users", tags=["Users"])


class UserGroupsUpdate(BaseModel):
    group_names: List[str]


@router.get("/me", response_model=UserResponse)
def read_user_me(current_user: User = Depends(get_current_user)):
    return current_user


# Admin-only route to create new managers or admins
@router.post("/", response_model=UserResponse)
@router.post("", response_model=UserResponse)
def create_user(
    user_in: UserCreate, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin"]))
):
    db_user = db.query(User).filter(User.email == user_in.email).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    hashed_pwd = hash_password(user_in.password)
    new_user = User(
        email=user_in.email,
        password_hash=hashed_pwd,
        full_name=user_in.full_name,
        role=user_in.role,
        is_active=user_in.is_active
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Journalisation de l'audit de création
    log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="user_created",
        entity_type="user",
        entity_id=str(new_user.id),
        details={
            "created_email": new_user.email,
            "role": new_user.role,
            "full_name": new_user.full_name,
            "is_active": new_user.is_active
        },
        request=request
    )

    return new_user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_in: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin"]))
):
    """
    Modification administrateur d'un utilisateur (rôle, statut actif/désactivé, etc.).
    Journalise 'user_role_changed', 'user_deactivated', et 'user_updated'.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur non trouvé")

    old_role = user.role
    old_active = user.is_active

    if user_in.role is not None and user_in.role != old_role:
        user.role = user_in.role
        log_audit_event(
            db=db,
            actor_user_id=current_user.id,
            action="user_role_changed",
            entity_type="user",
            entity_id=str(user.id),
            details={
                "target_email": user.email,
                "old_role": old_role,
                "new_role": user.role
            },
            request=request
        )

    if user_in.is_active is not None and user_in.is_active != old_active:
        user.is_active = user_in.is_active
        if not user.is_active:
            log_audit_event(
                db=db,
                actor_user_id=current_user.id,
                action="user_deactivated",
                entity_type="user",
                entity_id=str(user.id),
                details={
                    "target_email": user.email,
                    "reason": "admin_action"
                },
                request=request
            )

    if user_in.full_name is not None:
        user.full_name = user_in.full_name
    if user_in.password:
        user.password_hash = hash_password(user_in.password)

    db.commit()
    db.refresh(user)

    log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="user_updated",
        entity_type="user",
        entity_id=str(user.id),
        details={
            "target_email": user.email,
            "role": user.role,
            "is_active": user.is_active
        },
        request=request
    )

    return user


@router.put("/{user_id}/groups", response_model=UserResponse)
def update_user_groups(
    user_id: int,
    groups_in: UserGroupsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin"]))
):
    """
    Affectation des groupes de sécurité d'un utilisateur.
    Journalise 'user_groups_changed'.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur non trouvé")

    old_groups = [g.name for g in user.security_groups]
    new_groups = db.query(SecurityGroup).filter(SecurityGroup.name.in_(groups_in.group_names)).all()
    user.security_groups = new_groups
    db.commit()
    db.refresh(user)

    log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="user_groups_changed",
        entity_type="user",
        entity_id=str(user.id),
        details={
            "target_email": user.email,
            "old_groups": old_groups,
            "new_groups": [g.name for g in new_groups]
        },
        request=request
    )

    return user


@router.post("/{user_id}/unlock")
def unlock_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin"]))
):
    """
    Déverrouillage manuel d'un compte utilisateur verrouillé par la protection anti-bruteforce.
    Réservé aux administrateurs. Réinitialise le compteur d'échecs en purgeant les tentatives de connexion.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur non trouvé")

    # Purge des échecs enregistrés pour cet email
    db.query(LoginAttempt).filter(LoginAttempt.email_lower == user.email.lower()).delete(synchronize_session=False)
    db.commit()

    log_audit_event(
        db=db,
        actor_user_id=current_user.id,
        action="account_unlocked",
        entity_type="user",
        entity_id=str(user.id),
        details={"unlocked_email": user.email, "admin_email": current_user.email},
        request=request
    )

    return {"detail": f"Compte {user.email} déverrouillé avec succès"}
