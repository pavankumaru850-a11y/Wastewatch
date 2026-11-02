"""Municipal workflow state machine. Every status change goes through
change_status(): it validates the transition, records StatusHistory and an
audit row, and notifies the citizen. Nothing else may set report.status."""
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import ReportStatus as S, RoleEnum, StatusHistory, WasteReport, RoleEnum as R
from . import audit_service, notification_service

# NEW -> AI_DETECTED -> STAFF_REVIEW -> VERIFIED -> ASSIGNED -> IN_PROGRESS
#     -> CLEANED -> CLEANUP_VERIFICATION -> CLOSED ; REJECTED from any pre-cleanup step.
TRANSITIONS: dict[S, set[S]] = {
    S.NEW: {S.AI_DETECTED, S.STAFF_REVIEW, S.VERIFIED, S.REJECTED, S.NOT_WASTE},
    S.AI_DETECTED: {S.STAFF_REVIEW, S.VERIFIED, S.REJECTED, S.NOT_WASTE},
    S.STAFF_REVIEW: {S.VERIFIED, S.REJECTED, S.NOT_WASTE},
    S.VERIFIED: {S.ASSIGNED, S.REJECTED, S.NOT_WASTE},
    S.NOT_WASTE: {S.NEW},  # admin correction: the AI was wrong, it really is waste
    S.ASSIGNED: {S.IN_PROGRESS, S.VERIFIED, S.REJECTED},
    S.IN_PROGRESS: {S.CLEANED},
    S.CLEANED: {S.CLEANUP_VERIFICATION},
    S.CLEANUP_VERIFICATION: {S.CLOSED, S.IN_PROGRESS},  # back to IN_PROGRESS if cleanup insufficient
    S.COMPLETED: {S.CLOSED},  # legacy status from v1 data
    S.CLOSED: set(), S.REJECTED: set(),
}
# Which roles may move INTO a status (admin may do everything).
STAFF_TARGETS = {S.NOT_WASTE, S.STAFF_REVIEW, S.VERIFIED, S.IN_PROGRESS, S.CLEANED, S.CLEANUP_VERIFICATION, S.CLOSED, S.REJECTED}
NOTIFY_CITIZEN = {
    S.VERIFIED: "Your report was verified", S.ASSIGNED: "Cleanup has been assigned",
    S.CLEANED: "Cleanup completed", S.CLOSED: "Your report has been closed",
    S.REJECTED: "Your report was rejected",
}


def allowed_next(status: S) -> list[str]:
    return sorted(s.value for s in TRANSITIONS.get(status, set()))


def change_status(db: Session, report: WasteReport, new_status: S, user, remarks: str | None = None,
                  ip: str | None = None) -> WasteReport:
    old = report.status
    if new_status not in TRANSITIONS.get(old, set()):
        raise HTTPException(400, f"Cannot move a report from {old.value} to {new_status.value}. "
                                 f"Allowed: {', '.join(allowed_next(old)) or 'none'}.")
    if user.role == RoleEnum.STAFF and new_status not in STAFF_TARGETS:
        raise HTTPException(403, "Staff are not permitted to set this status.")
    if user.role == RoleEnum.STAFF and old == S.CLEANUP_VERIFICATION and new_status in (S.CLOSED, S.IN_PROGRESS):
        # Separation of duties: whoever did the cleanup must not be the one who signs it off.
        from ..models import CompletionReport
        done_by = db.query(CompletionReport.staff_id).filter(CompletionReport.report_id == report.id) \
                    .order_by(CompletionReport.id.desc()).first()
        if done_by and done_by[0] == user.id:
            raise HTTPException(403, "Cleanup must be verified by a different staff member or an admin.")
    if new_status == S.REJECTED and not (remarks or "").strip():
        raise HTTPException(400, "A reason is required to reject a report.")
    if new_status == S.NOT_WASTE:
        report.is_waste = False          # keep the flag and the status in step
    elif old == S.NOT_WASTE:
        report.is_waste = True
    report.status = new_status
    report.updated_at = datetime.utcnow()
    db.add(StatusHistory(report_id=report.id, old_status=old.value, new_status=new_status.value,
                         changed_by=user.id, remarks=remarks))
    db.commit()
    audit_service.log(db, user.id, f"STATUS_{new_status.value}", report.id, remarks, old.value, new_status.value, ip)
    if new_status in NOTIFY_CITIZEN:
        notification_service.notify(db, report.user_id, NOTIFY_CITIZEN[new_status], remarks, "status", report.id)
    db.refresh(report)
    return report
