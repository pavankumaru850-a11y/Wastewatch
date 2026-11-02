"""Hotspots: clusters of repeated reports within hotspot_radius_m. A
hotspot is created once >= hotspot_min_reports reports (excluding rejected)
sit within the radius of an existing hotspot centroid or of each other."""
from collections import Counter
from datetime import datetime

from sqlalchemy.orm import Session

from ..models import Hotspot, ReportStatus, WasteReport
from ..utils.gps_utils import haversine_meters
from .scoring_service import SEVERITY_ORDER


def _nearby_reports(db: Session, lat: float, lng: float, radius_m: float, exclude_id: int | None = None):
    pad = radius_m / 111_000 * 1.5 + 1e-5
    q = db.query(WasteReport).filter(
        WasteReport.latitude.between(lat - pad, lat + pad),
        WasteReport.longitude.between(lng - pad * 1.5, lng + pad * 1.5),  # generous for lat<60deg
        WasteReport.status.notin_([ReportStatus.REJECTED, ReportStatus.NOT_WASTE]),
    )
    if exclude_id is not None:
        q = q.filter(WasteReport.id != exclude_id)
    return [r for r in q.all() if haversine_meters(lat, lng, r.latitude, r.longitude) <= radius_m]


def refresh_hotspot(db: Session, hotspot: Hotspot) -> Hotspot:
    members = db.query(WasteReport).filter(WasteReport.hotspot_id == hotspot.id).all()
    if not members:
        return hotspot
    hotspot.total_reports = len(members)
    hotspot.latitude = sum(m.latitude for m in members) / len(members)
    hotspot.longitude = sum(m.longitude for m in members) / len(members)
    hotspot.first_report_at = min(m.created_at for m in members)
    hotspot.last_report_at = max(m.created_at for m in members)
    types = Counter(m.waste_type for m in members if m.waste_type)
    hotspot.dominant_waste_type = types.most_common(1)[0][0] if types else None
    sev = [m.severity for m in members if m.severity in SEVERITY_ORDER]
    hotspot.severity = max(sev, key=SEVERITY_ORDER.index) if sev else "LOW"
    hotspot.priority_score = max((m.priority_score or 0) for m in members)
    open_ = [m for m in members if m.status not in (ReportStatus.CLOSED, ReportStatus.COMPLETED, ReportStatus.CLEANED)]
    hotspot.cleanup_count = len(members) - len(open_)
    hotspot.current_status = "ACTIVE" if open_ else "CLEANED"
    db.commit()
    return hotspot


def assign_hotspot(db: Session, report: WasteReport, settings: dict) -> Hotspot | None:
    """Attach report to a hotspot if one is near; else create one when enough
    neighbours exist. Returns the hotspot or None."""
    radius, min_reports = settings["hotspot_radius_m"], settings["hotspot_min_reports"]
    existing = None
    for h in db.query(Hotspot).all():
        if haversine_meters(report.latitude, report.longitude, h.latitude, h.longitude) <= radius:
            existing = h
            break
    if existing is None:
        neighbours = _nearby_reports(db, report.latitude, report.longitude, radius, exclude_id=report.id)
        if len(neighbours) + 1 < min_reports:
            return None
        existing = Hotspot(latitude=report.latitude, longitude=report.longitude, total_reports=0)
        db.add(existing)
        db.flush()
        for n in neighbours:
            n.hotspot_id = existing.id
    report.hotspot_id = existing.id
    db.commit()
    return refresh_hotspot(db, existing)


def hotspot_color(severity: str) -> str:
    return {"LOW": "green", "MEDIUM": "yellow", "HIGH": "orange", "CRITICAL": "red"}.get(severity, "green")


def hotspot_history(db: Session, hotspot_id: int) -> list[dict]:
    """Timeline of the hotspot: each member report + its status changes."""
    from ..models import StatusHistory
    reports = db.query(WasteReport).filter(WasteReport.hotspot_id == hotspot_id).all()
    events = [{"at": r.created_at, "type": "REPORT", "report_id": r.id, "detail": r.waste_type or "unclassified"} for r in reports]
    ids = [r.id for r in reports]
    if ids:
        for h in db.query(StatusHistory).filter(StatusHistory.report_id.in_(ids)).all():
            events.append({"at": h.created_at, "type": "STATUS", "report_id": h.report_id, "detail": h.new_status})
    return sorted(events, key=lambda e: e["at"])
