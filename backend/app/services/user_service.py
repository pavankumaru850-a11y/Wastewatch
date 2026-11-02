"""services/user_service.py"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import RoleEnum, User
from ..schemas import RegisterRequest
from ..utils.security import hash_password, verify_password


def register_user(db: Session, data: RegisterRequest, role: RoleEnum = RoleEnum.CITIZEN) -> User:
    existing = db.query(User).filter(User.email == str(data.email).lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")
    user = User(
        name=data.name,
        email=str(data.email).lower(),
        phone=data.phone,
        password_hash=hash_password(data.password),
        role=role,  # self-registration is ALWAYS a citizen; staff/admin are created by an admin
        village=data.village,
        district=data.district,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == str(email).lower()).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated.")
    return user
