"""services/report_service.py -- report creation and lifecycle. Reports
are always saved even if AI detection is unavailable or finds nothing --
a citizen's photo + GPS is real data worth keeping and reviewing
manually; it just won't have an AI-assigned waste_type yet."""
from datetime import datetime, timedelta

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..models import (
    CleanupVerification, WasteReport, DetectionItem, StaffAssignment, CompletionReport,
    ReportStatus, PriorityEnum, User,
)
from ..config import get_settings, scoring_config
from ..models import RoleEnum, StatusHistory
from ..utils.file_utils import physical_path, save_upload
from ..utils.gps_utils import validate_coordinates, haversine_meters
from . import (geocode_service, detection_service, audit_service, notification_service, duplicate_service,
               hotspot_service, scoring_service, similarity_service, workflow_service)
from .scoring_service import confidence_level

def staff_touched(db, report_id: int, staff_id: int) -> bool:
    """True if this staff member ever changed the report's status (so they keep read access after handing it on/closing it)."""
    return db.query(StatusHistory.id).filter(StatusHistory.report_id == report_id, StatusHistory.changed_by == staff_id).first() is not None


def waste_only(q):
    """Restrict a WasteReport query to real waste (everything except reports the AI/admin marked NOT_WASTE)."""
    return q.filter(WasteReport.status != ReportStatus.NOT_WASTE)


REVIEW_QUEUE = (ReportStatus.NEW, ReportStatus.AI_DETECTED, ReportStatus.STAFF_REVIEW, ReportStatus.VERIFIED)


def create_report(
    db: Session, current_user: User, image: UploadFile,
    latitude: float, longitude: float,
    description: str | None = None, address: str | None = None,
    village: str | None = None, district: str | None = None,
    gps_accuracy: float | None = None, client_uuid: str | None = None,
    ip: str | None = None,
) -> tuple[WasteReport, str | None]:
    """Full pipeline: validate -> save -> quality -> detect -> hash ->
    duplicate check -> hotspot -> severity -> priority -> store -> notify.
    The report is ALWAYS stored (photo + GPS is real evidence) even when AI is
    unavailable or finds nothing; it then simply has no waste_type yet."""
    validate_coordinates(latitude, longitude)
    if client_uuid:  # idempotent offline sync: a retry returns the original report
        existing = db.query(WasteReport).filter(WasteReport.client_uuid == client_uuid).first()
        if existing:
            return existing, None
    settings = get_settings(db)
    if current_user.role == RoleEnum.CITIZEN:
        since = datetime.utcnow() - timedelta(hours=1)
        recent = db.query(WasteReport).filter(WasteReport.user_id == current_user.id, WasteReport.created_at >= since).count()
        if recent >= settings["max_reports_per_hour"]:
            raise HTTPException(status_code=429, detail="You have submitted many reports in the last hour. Please try again later.")
    image_path = save_upload(image, settings)          # stored (URL-style) path
    disk_path = physical_path(image_path)               # file on disk, for the AI + hashing
    ai = detection_service.run_detection(disk_path, settings)
    geo = geocode_service.lookup(latitude, longitude) or {}
    detections = ai["detections"] if ai["ok"] else []
    waste_type, confidence = detection_service.summarize_primary_class(detections)
    try:
        img_hash = similarity_service.dhash(disk_path)
    except Exception:  # noqa: BLE001
        img_hash = None

    is_waste = ai.get("is_waste") if ai["ok"] else None  # None = AI could not decide -> human review
    not_waste = ai["ok"] and is_waste is False
    if not_waste:
        waste_type, confidence = None, ai.get("non_waste_confidence")

    report = WasteReport(
        user_id=current_user.id, image_path=image_path, waste_type=waste_type, confidence=confidence,
        is_waste=is_waste,
        latitude=latitude, longitude=longitude, gps_accuracy=gps_accuracy, address=address or geo.get("address"),
        village=village or geo.get("village") or current_user.village, district=district or geo.get("district") or current_user.district,
        town=geo.get("town"), state=geo.get("state"), country=geo.get("country"),
        description=description, status=ReportStatus.NOT_WASTE if not_waste else ReportStatus.NEW, image_hash=img_hash,
        priority=PriorityEnum.LOW if not_waste else PriorityEnum.MEDIUM,
        object_count=len(detections), detection_summary=detection_service.summarize_text(detections),
        model_version=ai["model_version"], confidence_level=confidence_level(confidence),
        quality_ok=ai.get("code") != "IMAGE_QUALITY_LOW", client_uuid=client_uuid,
    )
    db.add(report)
    db.flush()
    for d in detections:
        db.add(DetectionItem(report_id=report.id, class_name=d["class_name"], confidence=d["confidence"],
                             x1=d["box"]["x1"], y1=d["box"]["y1"], x2=d["box"]["x2"], y2=d["box"]["y2"]))
    db.commit()

    if not_waste:
        # NOT WASTE: keep the photo + details in the separate "Not Waste" store. No duplicate check, hotspot,
        # severity, priority or deadline, and NO staff/admin notification -- it is not part of the waste workflow.
        db.add(StatusHistory(report_id=report.id, old_status="NEW", new_status="NOT_WASTE",
                             changed_by=current_user.id, remarks="AI: not waste"))
        db.commit()
        db.refresh(report)
        audit_service.log(db, current_user.id, "REPORT_NOT_WASTE", report.id, "AI decided: not waste", ip=ip)
        notification_service.notify(db, current_user.id, "Photo is not waste", ai["message"], "not_waste", report.id)
        return report, ai["message"]

    checks = duplicate_service.run_duplicate_check(db, report, settings)
    hotspot = hotspot_service.assign_hotspot(db, report, settings)
    sev = scoring_service.compute_severity(detections, repeat_count=len(checks), in_hotspot=hotspot is not None,
                                           img_size=ai.get("image_size"))
    pri = scoring_service.compute_priority(detections, sev["score"], repeat_count=len(checks),
                                           hotspot_reports=hotspot.total_reports if hotspot else 0)
    cfg = scoring_config()
    report.severity_score, report.severity = sev["score"], sev["level"]
    report.priority_score, report.priority = pri["score"], PriorityEnum(pri["level"])
    report.deadline = datetime.utcnow() + timedelta(hours=cfg["deadline_hours"][pri["level"]])
    if detections:
        report.status = ReportStatus.AI_DETECTED
        db.add(StatusHistory(report_id=report.id, old_status="NEW", new_status="AI_DETECTED",
                             changed_by=current_user.id, remarks="AI detection completed"))
    db.commit()
    if hotspot:
        hotspot_service.refresh_hotspot(db, hotspot)
    db.refresh(report)

    audit_service.log(db, current_user.id, "REPORT_CREATED", report.id, report.detection_summary, ip=ip)
    notification_service.notify(db, current_user.id, "Report submitted", ai["message"], "report", report.id)
    _notify_waste_found(db, report, ai_confirmed=is_waste is True)
    if report.priority == PriorityEnum.CRITICAL:
        notification_service.notify_role(db, [RoleEnum.STAFF, RoleEnum.ADMIN], f"Critical report #{report.id}",
                                         report.detection_summary, "critical", report.id)
    if hotspot and hotspot.total_reports == get_settings(db)["hotspot_min_reports"]:
        notification_service.notify_role(db, [RoleEnum.ADMIN], f"New hotspot #{hotspot.id}",
                                         f"{hotspot.total_reports} reports nearby", "hotspot", report.id)
    return report, ai["message"]


def _notify_waste_found(db: Session, report: WasteReport, ai_confirmed: bool) -> None:
    """Staff + admin notification for a real waste report, with the details they need."""
    place = ", ".join(x for x in (report.village, report.district) if x) or f"{report.latitude:.5f}, {report.longitude:.5f}"
    conf = f", confidence {report.confidence:.0%}" if report.confidence is not None else ""
    title = f"Waste detected - report #{report.id}" if ai_confirmed else f"New report #{report.id} (needs review)"
    notification_service.notify_role(
        db, [RoleEnum.STAFF, RoleEnum.ADMIN], title,
        f"{place}. {report.severity or 'LOW'} severity, priority {report.priority_score}{conf}.", "new_report", report.id)


def reclassify(db: Session, report_id: int, is_waste: bool, user: User, remarks: str | None = None) -> WasteReport:
    """Admin correction of the AI decision. Not waste -> waste re-enters the normal waste workflow
    (hotspot, priority, notification). Waste -> not waste moves it to the separate Not Waste store."""
    report = get_report_or_404(db, report_id)
    if is_waste and report.status == ReportStatus.NOT_WASTE:
        report.is_waste = True
        workflow_service.change_status(db, report, ReportStatus.NEW, user, remarks or "Admin: this is waste")
        settings = get_settings(db)
        checks = duplicate_service.run_duplicate_check(db, report, settings)
        hotspot = hotspot_service.assign_hotspot(db, report, settings)
        cfg = scoring_config()
        report.severity_score, report.severity = 0.0, "LOW"
        report.priority_score, report.priority = 0.0, PriorityEnum.MEDIUM  # no AI boxes: a human will set the priority
        report.deadline = datetime.utcnow() + timedelta(hours=cfg["deadline_hours"]["MEDIUM"])
        db.commit()
        if hotspot:
            hotspot_service.refresh_hotspot(db, hotspot)
        db.refresh(report)
        _notify_waste_found(db, report, ai_confirmed=False)
    elif not is_waste and report.status != ReportStatus.NOT_WASTE:
        report.is_waste = False
        workflow_service.change_status(db, report, ReportStatus.NOT_WASTE, user, remarks or "Admin: not waste")
    else:
        raise HTTPException(status_code=400, detail="The report is already in that category.")
    audit_service.log(db, user.id, "RECLASSIFIED", report_id, f"is_waste={is_waste}")
    db.refresh(report)
    return report


def list_reports(
    db: Session, status=None, waste_type=None, village=None, district=None, priority=None,
    staff_id=None, user_id=None, severity=None, hotspot_id=None, duplicate=None,
    min_confidence=None, date_from=None, date_to=None, search=None, assigned_to=None,
    is_waste=None, include_not_waste=False,
) -> list[WasteReport]:
    """By default NOT_WASTE reports are left out (they are stored separately). Ask for them with
    is_waste=False or status=NOT_WASTE; citizens pass include_not_waste=True to see their own."""
    q = db.query(WasteReport)
    wants_not_waste = is_waste is False or str(getattr(status, "value", status) or "") == "NOT_WASTE"
    if wants_not_waste:
        q = q.filter(WasteReport.status == ReportStatus.NOT_WASTE)
    elif not include_not_waste:
        q = waste_only(q)
    if is_waste is True:
        q = q.filter(WasteReport.is_waste == True)  # noqa: E712
    if status and not wants_not_waste:
        q = q.filter(WasteReport.status == status)
    if waste_type:
        q = q.filter(WasteReport.waste_type == waste_type)
    if village:
        q = q.filter(WasteReport.village == village)
    if district:
        q = q.filter(WasteReport.district == district)
    if priority:
        q = q.filter(WasteReport.priority == priority)
    if severity:
        q = q.filter(WasteReport.severity == severity)
    if hotspot_id:
        q = q.filter(WasteReport.hotspot_id == hotspot_id)
    if duplicate is not None:
        q = q.filter(WasteReport.is_possible_duplicate == duplicate)
    if min_confidence is not None:
        q = q.filter(WasteReport.confidence >= min_confidence)
    if date_from:
        q = q.filter(WasteReport.created_at >= date_from)
    if date_to:
        q = q.filter(WasteReport.created_at <= date_to)
    if search:
        like = f"%{search}%"
        q = q.filter((WasteReport.address.ilike(like)) | (WasteReport.village.ilike(like)) |
                     (WasteReport.description.ilike(like)) | (WasteReport.detection_summary.ilike(like)))
    if user_id:
        q = q.filter(WasteReport.user_id == user_id)
    if assigned_to and not staff_id:  # admin filter: reports assigned to a given staff member
        q = q.join(StaffAssignment, StaffAssignment.report_id == WasteReport.id).filter(StaffAssignment.staff_id == assigned_to)
    if staff_id:
        # staff see (a) reports assigned to them and (b) the unassigned review queue
        from sqlalchemy import or_
        q = q.outerjoin(StaffAssignment, StaffAssignment.report_id == WasteReport.id).filter(or_(
            StaffAssignment.staff_id == staff_id,
            (StaffAssignment.id.is_(None)) & WasteReport.status.in_(REVIEW_QUEUE),
            WasteReport.status == ReportStatus.CLEANUP_VERIFICATION,  # verification queue: any staff may check finished cleanups
            WasteReport.id.in_(db.query(StatusHistory.report_id).filter(StatusHistory.changed_by == staff_id))))  # reports I worked on
    return q.order_by(WasteReport.priority_score.desc().nullslast(), WasteReport.created_at.desc()).all()


def get_report_or_404(db: Session, report_id: int) -> WasteReport:
    report = db.query(WasteReport).filter(WasteReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    return report


def update_report(db: Session, report_id: int, updates: dict, user=None) -> WasteReport:
    report = get_report_or_404(db, report_id)
    new_status = updates.pop("status", None)
    for key, value in updates.items():
        if value is not None:
            old = getattr(report, key)
            setattr(report, key, value)
            if user:
                audit_service.log(db, user.id, "REPORT_MODIFIED", report_id, key, str(old), str(value))
    report.updated_at = datetime.utcnow()
    db.commit()
    if new_status is not None and new_status != report.status:
        workflow_service.change_status(db, report, new_status, user, "Updated by admin")
    db.refresh(report)
    return report


def assign_staff(db: Session, report_id: int, staff_id: int, assigned_by_id: int, remarks: str | None) -> WasteReport:
    report = get_report_or_404(db, report_id)
    staff = db.query(User).filter(User.id == staff_id, User.is_active == True).first()  # noqa: E712
    if not staff or staff.role not in (RoleEnum.STAFF, RoleEnum.ADMIN):
        raise HTTPException(status_code=404, detail="Staff user not found.")
    admin = db.query(User).get(assigned_by_id)
    if report.status in (ReportStatus.NEW, ReportStatus.AI_DETECTED, ReportStatus.STAFF_REVIEW):
        workflow_service.change_status(db, report, ReportStatus.VERIFIED, admin, "Auto-verified on assignment")
    existing = db.query(StaffAssignment).filter(StaffAssignment.report_id == report_id).first()
    if existing:
        existing.staff_id, existing.assigned_by, existing.assigned_at, existing.remarks = staff_id, assigned_by_id, datetime.utcnow(), remarks
    else:
        db.add(StaffAssignment(report_id=report_id, staff_id=staff_id, assigned_by=assigned_by_id, remarks=remarks))
    db.commit()
    if report.status != ReportStatus.ASSIGNED:
        workflow_service.change_status(db, report, ReportStatus.ASSIGNED, admin, remarks)
    audit_service.log(db, assigned_by_id, "ASSIGN", report_id, f"assigned to staff #{staff_id}", None, str(staff_id))
    notification_service.notify(db, staff_id, "New assignment", f"Report #{report_id}", "assignment", report_id)
    db.refresh(report)
    return report


def update_status(db: Session, report_id: int, new_status: str, current_user: User, remarks: str | None,
                  ip: str | None = None) -> WasteReport:
    report = get_report_or_404(db, report_id)
    if current_user.role == RoleEnum.STAFF:
        assignment = db.query(StaffAssignment).filter(StaffAssignment.report_id == report_id).first()
        unassigned_review = report.status in (ReportStatus.NEW, ReportStatus.AI_DETECTED, ReportStatus.STAFF_REVIEW, ReportStatus.CLEANUP_VERIFICATION)
        if not unassigned_review and (not assignment or assignment.staff_id != current_user.id):
            raise HTTPException(status_code=403, detail="This report is not assigned to you.")
    return workflow_service.change_status(db, report, ReportStatus(new_status), current_user, remarks, ip)


def upload_before_image(db: Session, report_id: int, user: User, image: UploadFile) -> CleanupVerification:
    report = get_report_or_404(db, report_id)
    _require_assigned(db, report, user)
    path = save_upload(image, get_settings(db), subdir="before")
    cv = _get_or_create_cv(db, report_id)
    cv.before_image = path
    db.commit()
    audit_service.log(db, user.id, "BEFORE_IMAGE_UPLOADED", report_id)
    return cv


def _require_assigned(db, report, user):
    if user.role == RoleEnum.ADMIN:
        return
    a = db.query(StaffAssignment).filter(StaffAssignment.report_id == report.id).first()
    if not a or a.staff_id != user.id:
        raise HTTPException(status_code=403, detail="This report is not assigned to you.")


def _get_or_create_cv(db, report_id) -> CleanupVerification:
    cv = db.query(CleanupVerification).filter(CleanupVerification.report_id == report_id).first()
    if not cv:
        cv = CleanupVerification(report_id=report_id)
        db.add(cv)
        db.flush()
    return cv


def complete_report(
    db: Session, report_id: int, current_user: User, completion_image: UploadFile,
    remarks: str | None, latitude: float | None, longitude: float | None, ip: str | None = None,
) -> CompletionReport:
    """Staff uploads the AFTER image. Detection runs on before (original report
    photo unless a dedicated before image was uploaded) and after; the
    comparison is stored as a CleanupVerification and the report moves
    IN_PROGRESS -> CLEANED -> CLEANUP_VERIFICATION. Admin/staff-verifier then closes it."""
    report = get_report_or_404(db, report_id)
    _require_assigned(db, report, current_user)
    if report.status != ReportStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Start the cleanup (IN_PROGRESS) before completing it.")
    settings = get_settings(db)
    after_path = save_upload(completion_image, settings, subdir="after")
    completion = CompletionReport(report_id=report_id, staff_id=current_user.id, completion_image=after_path,
                                  remarks=remarks, latitude=latitude, longitude=longitude)
    db.add(completion)
    assignment = db.query(StaffAssignment).filter(StaffAssignment.report_id == report_id).first()
    if assignment:
        assignment.completed_at = datetime.utcnow()
    cv = _get_or_create_cv(db, report_id)
    cv.after_image = after_path
    cv.before_image = cv.before_image or report.image_path
    cv.remarks = remarks
    before = detection_service.run_detection(physical_path(cv.before_image), settings, skip_quality=True)
    after = detection_service.run_detection(physical_path(after_path), settings, skip_quality=True)
    if before["ok"] and after["ok"]:
        cv.analysis_available = True
        cv.before_detection_count = before["object_count"]
        cv.after_detection_count = after["object_count"]
        cv.improvement_percentage = compare_counts(before["object_count"], after["object_count"])
    else:  # model unavailable: never invent numbers; a human must verify by eye
        cv.analysis_available = False
    db.commit()
    workflow_service.change_status(db, report, ReportStatus.CLEANED, current_user, remarks, ip)
    workflow_service.change_status(db, report, ReportStatus.CLEANUP_VERIFICATION, current_user, "Awaiting verification", ip)
    audit_service.log(db, current_user.id, "CLEANUP_COMPLETED", report_id, remarks)
    db.refresh(completion)
    return completion


def compare_counts(before: int, after: int) -> float | None:
    """improvement % = (before-after)/before*100, clamped to [-100, 100]. None if no baseline."""
    if before <= 0:
        return None
    return round(max(-100.0, min(100.0, (before - after) / before * 100)), 1)


def close_after_verification(db: Session, report_id: int, user: User, approve: bool, remarks: str | None,
                             ip: str | None = None) -> CleanupVerification:
    report = get_report_or_404(db, report_id)
    cv = db.query(CleanupVerification).filter(CleanupVerification.report_id == report_id).first()
    if not cv or report.status != ReportStatus.CLEANUP_VERIFICATION:
        raise HTTPException(status_code=400, detail="This report is not awaiting cleanup verification.")
    cv.verified_by, cv.verified_at = user.id, datetime.utcnow()
    if remarks:
        cv.remarks = remarks
    db.commit()
    target = ReportStatus.CLOSED if approve else ReportStatus.IN_PROGRESS
    workflow_service.change_status(db, report, target, user, remarks, ip)
    if report.hotspot_id:
        from ..models import Hotspot
        hotspot_service.refresh_hotspot(db, db.query(Hotspot).get(report.hotspot_id))
    db.refresh(cv)
    return cv
