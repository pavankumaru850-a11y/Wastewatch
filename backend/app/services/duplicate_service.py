"""Duplicate detection: GPS distance + time window + category + perceptual
hash. Reports are FLAGGED, never deleted. Staff confirm / dismiss / merge."""
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import DuplicateCheck, ReportStatus, WasteReport
from ..utils.gps_utils import haversine_meters
from . import audit_service
from .similarity_service import hamming


def find_candidates(db: Session, report: WasteReport, settings: dict) -> list[DuplicateCheck]:
    dist_limit = settings["duplicate_distance_m"]
    window = datetime.utcnow() - timedelta(hours=settings["duplicate_time_window_hours"])
    pad = dist_limit / 111_000 * 1.5 + 1e-5
    q = db.query(WasteReport).filter(
        WasteReport.id != report.id, WasteReport.created_at >= window,
        WasteReport.status.notin_([ReportStatus.REJECTED, ReportStatus.CLOSED, ReportStatus.NOT_WASTE]),
        WasteReport.latitude.between(report.latitude - pad, report.latitude + pad),
        WasteReport.longitude.between(report.longitude - pad * 1.5, report.longitude + pad * 1.5),
    )
    checks = []
    for c in q.all():
        d = haversine_meters(report.latitude, report.longitude, c.latitude, c.longitude)
        if d > dist_limit:
            continue
        hd = hamming(report.image_hash, c.image_hash)
        same_cat = bool(report.waste_type and report.waste_type == c.waste_type)
        similar_image = hd is not None and hd <= settings["duplicate_hash_max_distance"]
        # Distance + time window are hard gates. On top of that we need real evidence of "same thing":
        #   * a similar photo (perceptual hash), OR
        #   * the same category from practically the same spot (<= duplicate_close_distance_m).
        # Category alone is NOT enough: there are only a handful of categories, so two different piles
        # on the same street would otherwise be flagged constantly.
        if not (similar_image or (same_cat and d <= settings["duplicate_close_distance_m"])):
            continue
        checks.append(DuplicateCheck(
            report_id=report.id, candidate_id=c.id, distance_m=round(d, 1), hash_distance=hd,
            time_diff_minutes=round(abs((report.created_at - c.created_at).total_seconds()) / 60, 1),
            same_category=same_cat))
    return checks


def run_duplicate_check(db: Session, report: WasteReport, settings: dict) -> list[DuplicateCheck]:
    checks = find_candidates(db, report, settings)
    for c in checks:
        db.add(c)
    if checks:
        report.is_possible_duplicate = True
        report.is_duplicate = True  # legacy flag kept in sync
        report.duplicate_of_id = min(checks, key=lambda c: c.distance_m).candidate_id
    db.commit()
    return checks


def decide(db: Session, check_id: int, decision: str, user, ip: str | None = None) -> DuplicateCheck:
    if decision not in {"CONFIRMED", "NOT_DUPLICATE", "MERGED"}:
        raise HTTPException(400, "Decision must be CONFIRMED, NOT_DUPLICATE or MERGED.")
    check = db.query(DuplicateCheck).filter(DuplicateCheck.id == check_id).first()
    if not check:
        raise HTTPException(404, "Duplicate check not found.")
    report = db.query(WasteReport).get(check.report_id)
    check.decision, check.decided_by, check.decided_at = decision, user.id, datetime.utcnow()
    if decision == "NOT_DUPLICATE":
        pending = db.query(DuplicateCheck).filter(
            DuplicateCheck.report_id == report.id, DuplicateCheck.id != check.id,
            DuplicateCheck.decision.in_(["PENDING", "CONFIRMED", "MERGED"])).count()
        if not pending:
            report.is_possible_duplicate = False
            report.is_duplicate = False
            report.duplicate_of_id = None
    if decision == "MERGED":
        # Merge keeps the older report as the primary and closes the newer one as a
        # duplicate; the record and its image are retained for audit.
        primary = db.query(WasteReport).get(check.candidate_id)
        report.duplicate_of_id = primary.id
        report.is_duplicate = True
        if report.status not in (ReportStatus.REJECTED, ReportStatus.CLOSED):
            from .workflow_service import TRANSITIONS
            if ReportStatus.REJECTED in TRANSITIONS.get(report.status, set()):
                from ..models import StatusHistory
                db.add(StatusHistory(report_id=report.id, old_status=report.status.value,
                                     new_status="REJECTED", changed_by=user.id,
                                     remarks=f"Merged into report #{primary.id}"))
                report.status = ReportStatus.REJECTED
    db.commit()
    audit_service.log(db, user.id, f"DUPLICATE_{decision}", report.id,
                      f"check #{check.id} vs report #{check.candidate_id}", None, decision, ip)
    return check
