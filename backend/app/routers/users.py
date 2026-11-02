"""routers/users.py -- self-service profile endpoints. Broader user
management lives in routers/admin.py (admin-only)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User
from ..schemas import UserOut, ProfileUpdateRequest, ChangePasswordRequest
from ..utils.security import hash_password, verify_password

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def my_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserOut)
def update_profile(
    data: ProfileUpdateRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(current_user, key, value)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/change-password")
def change_password(
    data: ChangePasswordRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters.")
    current_user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"success": True, "detail": "Password updated."}
