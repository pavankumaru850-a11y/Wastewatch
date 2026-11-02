"""routers/auth.py"""
import logging
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User
from ..schemas import RegisterRequest, LoginRequest, TokenResponse, UserOut
from ..services import audit_service, user_service
from ..utils.security import create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = logging.getLogger("wastewatch.auth")

# Simple in-memory limiter: 10 failed logins / 5 min per IP. Fine for a single-process
# deployment; use Redis or a reverse-proxy limiter if you scale to several workers.
_FAILS: dict[str, deque] = defaultdict(deque)
WINDOW, MAX_FAILS = 300, 10


def _limited(ip: str) -> bool:
    q = _FAILS[ip]
    while q and time.time() - q[0] > WINDOW:
        q.popleft()
    return len(q) >= MAX_FAILS


@router.post("/register", response_model=UserOut)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """Public registration always creates a CITIZEN."""
    return user_service.register_user(db, data)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    if _limited(ip):
        raise HTTPException(status_code=429, detail="Too many failed attempts. Please try again later.")
    try:
        user = user_service.authenticate_user(db, data.email, data.password)
    except HTTPException:
        _FAILS[ip].append(time.time())
        log.warning("login failed ip=%s", ip)
        raise
    audit_service.log(db, user.id, "USER_LOGIN", None, None, ip=ip)
    return TokenResponse(access_token=create_access_token({"sub": str(user.id), "role": user.role.value}))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
