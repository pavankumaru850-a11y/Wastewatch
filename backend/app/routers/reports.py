"""routers/reports.py"""
from typing import Optional

from typing import Optional

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, Response
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_admin, require_staff
from ..database import get_db
from ..models import ReportStatus, User, RoleEnum
from ..schemas import (
    ReportOut, ReportUpdateRequest, AssignRequest, StatusUpdateRequest, CompletionOut,
    CleanupVerificationOut, CleanupDecision, ReclassifyRequest,
)
from ..services import report_service, pdf_service

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/export/pdf")
def export_pdf(
    status: Optional[str] = None,
    waste_type: Optional[str] = None,
    village: Optional[str] = None,
    district: Optional[str] = None,
    priority: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Route defined ABOVE /{report_id} on purpose -- otherwise FastAPI
    would try to parse 'export' as a report_id and 404."""
    filters = dict(status=status, waste_type=waste_type, village=village, district=district, priority=priority)
    if current_user.role == RoleEnum.CITIZEN:
        reports = report_service.list_reports(db, user_id=current_user.id, **filters)
    elif current_user.role == RoleEnum.STAFF:
        reports = report_service.list_reports(db, staff_id=current_user.id, **filters)
    else:
        reports = report_service.list_reports(db, **filters)

    pdf_bytes = pdf_service.build_report_pdf(reports, filters)
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=wastewatch_report_{__import__('datetime').datetime.utcnow().strftime('%Y%m%d')}.pdf"},
    )


@router.get("/export/csv")
def export_csv(status: Optional[str] = None, waste_type: Optional[str] = None, severity: Optional[str] = None,
               priority: Optional[str] = None, date_from: Optional[datetime] = None, date_to: Optional[datetime] = None,
               current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    from ..services import export_service, audit_service
    rows = _scope(current_user, db, status=status, waste_type=waste_type, severity=severity, priority=priority, date_from=date_from, date_to=date_to)
    audit_service.log(db, current_user.id, "EXPORT_CSV", None, f"{len(rows)} reports")
    return Response(export_service.to_csv(db, rows), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=wastewatch_reports.csv"})


@router.get("/export/xlsx")
def export_xlsx(status: Optional[str] = None, waste_type: Optional[str] = None, severity: Optional[str] = None,
                priority: Optional[str] = None, date_from: Optional[datetime] = None, date_to: Optional[datetime] = None,
                current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    from ..services import export_service, audit_service
    rows = _scope(current_user, db, status=status, waste_type=waste_type, severity=severity, priority=priority, date_from=date_from, date_to=date_to)
    audit_service.log(db, current_user.id, "EXPORT_XLSX", None, f"{len(rows)} reports")
    return Response(export_service.to_xlsx(db, rows),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=wastewatch_reports.xlsx"})


@router.post("", response_model=ReportOut)
def create_report(
    request: Request,
    image: UploadFile = File(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    gps_accuracy: Optional[float] = Form(None),
    description: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    village: Optional[str] = Form(None),
    district: Optional[str] = Form(None),
    client_uuid: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report, _msg = report_service.create_report(
        db, current_user, image, latitude, longitude, description, address, village, district,
        gps_accuracy=gps_accuracy, client_uuid=client_uuid, ip=request.client.host if request.client else None,
    )
    return report


def _scope(current_user, db, **f):
    if current_user.role == RoleEnum.CITIZEN:
        return report_service.list_reports(db, user_id=current_user.id, include_not_waste=True, **f)
    if current_user.role == RoleEnum.STAFF:
        return report_service.list_reports(db, staff_id=current_user.id, **f)
    return report_service.list_reports(db, **f)


@router.get("", response_model=list[ReportOut])
def list_reports(
    status: Optional[str] = None, waste_type: Optional[str] = None, village: Optional[str] = None,
    district: Optional[str] = None, priority: Optional[str] = None, severity: Optional[str] = None,
    hotspot_id: Optional[int] = None, duplicate: Optional[bool] = None, min_confidence: Optional[float] = None,
    date_from: Optional[datetime] = None, date_to: Optional[datetime] = None, search: Optional[str] = None,
    assigned_to: Optional[int] = None, is_waste: Optional[bool] = None, limit: int = 200, offset: int = 0,
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """RBAC enforced here: citizens see own, staff see assigned + review queue, admin all."""
    rows = _scope(current_user, db, status=status, waste_type=waste_type, village=village, district=district,
                  priority=priority, severity=severity, hotspot_id=hotspot_id, duplicate=duplicate,
                  min_confidence=min_confidence, date_from=date_from, date_to=date_to, search=search,
                  is_waste=is_waste, assigned_to=assigned_to if current_user.role == RoleEnum.ADMIN else None)
    return rows[offset: offset + min(limit, 500)]


@router.get("/{report_id}", response_model=ReportOut)
def get_report(report_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = report_service.get_report_or_404(db, report_id)
    _enforce_report_access(report, current_user, db)
    return report


@router.put("/{report_id}", response_model=ReportOut)
def update_report(
    report_id: int, data: ReportUpdateRequest,
    current_user: User = Depends(require_admin), db: Session = Depends(get_db),
):
    return report_service.update_report(db, report_id, data.model_dump(exclude_unset=True), current_user)


@router.post("/{report_id}/reclassify", response_model=ReportOut)
def reclassify_report(report_id: int, data: ReclassifyRequest,
                      current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Admin corrects the AI: mark a Not-Waste photo as waste (enters the waste workflow) or the reverse."""
    return report_service.reclassify(db, report_id, data.is_waste, current_user, data.remarks)


@router.post("/{report_id}/assign", response_model=ReportOut)
def assign_report(
    report_id: int, data: AssignRequest,
    current_user: User = Depends(require_admin), db: Session = Depends(get_db),
):
    return report_service.assign_staff(db, report_id, data.staff_id, current_user.id, data.remarks)


@router.put("/{report_id}/status", response_model=ReportOut)
def update_status(
    report_id: int, data: StatusUpdateRequest, request: Request,
    current_user: User = Depends(require_staff), db: Session = Depends(get_db),
):
    return report_service.update_status(db, report_id, data.status.value, current_user, data.remarks,
                                        request.client.host if request.client else None)


@router.post("/{report_id}/complete", response_model=CompletionOut)
def complete_report(
    report_id: int, request: Request,
    completion_image: UploadFile = File(...),
    remarks: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    current_user: User = Depends(require_staff),
    db: Session = Depends(get_db),
):
    return report_service.complete_report(
        db, report_id, current_user, completion_image, remarks, latitude, longitude,
        request.client.host if request.client else None,
    )


@router.post("/{report_id}/before-image", response_model=CleanupVerificationOut)
def before_image(report_id: int, image: UploadFile = File(...),
                 current_user: User = Depends(require_staff), db: Session = Depends(get_db)):
    return report_service.upload_before_image(db, report_id, current_user, image)


@router.get("/{report_id}/cleanup-verification", response_model=CleanupVerificationOut)
def get_cleanup(report_id: int, current_user: User = Depends(require_staff), db: Session = Depends(get_db)):
    from ..models import CleanupVerification
    report = report_service.get_report_or_404(db, report_id)
    _enforce_report_access(report, current_user, db)
    cv = db.query(CleanupVerification).filter(CleanupVerification.report_id == report_id).first()
    if not cv:
        raise HTTPException(404, "No cleanup evidence for this report yet.")
    return cv


@router.post("/{report_id}/cleanup-verification", response_model=CleanupVerificationOut)
def decide_cleanup(report_id: int, data: CleanupDecision, request: Request,
                   current_user: User = Depends(require_staff), db: Session = Depends(get_db)):
    """Approve -> CLOSED. Reject -> back to IN_PROGRESS. Any staff member other than the one who did the
    cleanup (or an admin) may decide; self-verification is refused."""
    report = report_service.get_report_or_404(db, report_id)
    _enforce_report_access(report, current_user, db)
    return report_service.close_after_verification(db, report_id, current_user, data.approve, data.remarks,
                                                   request.client.host if request.client else None)


@router.get("/{report_id}/history")
def status_history(report_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from ..models import StatusHistory
    from ..services import workflow_service
    report = report_service.get_report_or_404(db, report_id)
    _enforce_report_access(report, current_user, db)
    rows = db.query(StatusHistory).filter(StatusHistory.report_id == report_id).order_by(StatusHistory.created_at).all()
    return {"current": report.status.value, "allowed_next": workflow_service.allowed_next(report.status),
            "history": [{"old": r.old_status, "new": r.new_status, "by": r.changed_by, "remarks": r.remarks, "at": r.created_at} for r in rows]}


def _enforce_report_access(report, current_user: User, db: Session):
    from fastapi import HTTPException
    if current_user.role == RoleEnum.ADMIN:
        return
    if current_user.role == RoleEnum.CITIZEN and report.user_id == current_user.id:
        return
    if current_user.role == RoleEnum.STAFF:
        from ..models import StaffAssignment
        assignment = db.query(StaffAssignment).filter(StaffAssignment.report_id == report.id).first()
        if assignment and assignment.staff_id == current_user.id:
            return
        if not assignment and report.status in report_service.REVIEW_QUEUE:
            return
        if report.status == ReportStatus.CLEANUP_VERIFICATION:
            return  # verification queue is open to all staff (self-verification is blocked in the workflow)
        if report_service.staff_touched(db, report.id, current_user.id):
            return  # staff keep access to reports they worked on
    raise HTTPException(status_code=403, detail="You do not have permission to view this report.")
