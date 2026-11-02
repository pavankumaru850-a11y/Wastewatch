"""routers/duplicates.py -- staff review of possible duplicates."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..auth import require_staff
from ..database import get_db
from ..models import DuplicateCheck, User
from ..schemas import DuplicateCheckOut, DuplicateDecision
from ..services import duplicate_service

router = APIRouter(prefix="/api/duplicates", tags=["duplicates"])


@router.get("", response_model=list[DuplicateCheckOut])
def list_checks(decision: str | None = "PENDING", report_id: int | None = None,
                current_user: User = Depends(require_staff), db: Session = Depends(get_db)):
    q = db.query(DuplicateCheck)
    if decision:
        q = q.filter(DuplicateCheck.decision == decision)
    if report_id:
        q = q.filter(DuplicateCheck.report_id == report_id)
    return q.order_by(DuplicateCheck.created_at.desc()).limit(200).all()


@router.post("/{check_id}/decision", response_model=DuplicateCheckOut)
def decide(check_id: int, data: DuplicateDecision, request: Request,
           current_user: User = Depends(require_staff), db: Session = Depends(get_db)):
    return duplicate_service.decide(db, check_id, data.decision, current_user, request.client.host if request.client else None)
