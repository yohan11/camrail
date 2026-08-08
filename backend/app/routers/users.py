from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.schemas import User
from app.schemas.user import UserResponse, UserCreate
from app.deps import get_current_user, RoleChecker
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/me", response_model=UserResponse)
def read_user_me(current_user: User = Depends(get_current_user)):
    return current_user

# Admin-only route to create new managers or admins
@router.post("/", response_model=UserResponse)
def create_user(
    user_in: UserCreate, 
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
    return new_user
