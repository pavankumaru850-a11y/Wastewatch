"""routers/staff.py -- staff can only ever see their own assignments;
enforced by filtering on current_user.id server-side, never trusting a
staff_id from the client."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_staff
from ..database import get_db
from ..models import User, StaffAssignment, WasteReport, ReportStatus

router = APIRouter(prefix="/api/staff", tags=["staff"])


@router.get("/summary")
def my_summary(current_user: User = Depends(require_staff), db: Session = Depends(get_db)):
    q = (
        db.query(WasteReport)
        .join(StaffAssignment, StaffAssignment.report_id == WasteReport.id)
        .filter(StaffAssignment.staff_id == current_user.id)
    )
    return {
        "assigned": q.filter(WasteReport.status == ReportStatus.ASSIGNED).count(),
        "in_progress": q.filter(WasteReport.status == ReportStatus.IN_PROGRESS).count(),
        "completed": q.filter(WasteReport.status == ReportStatus.COMPLETED).count(),
        "total": q.count(),
    }
