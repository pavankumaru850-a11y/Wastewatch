"""routers/analytics.py -- GET /api/analytics/summary. Every number is a live aggregation over the
database (done in Python so it works on SQLite and PostgreSQL alike); nothing is a placeholder."""
from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_staff
from ..database import get_db
from ..models import CleanupVerification, Hotspot, ReportStatus, RoleEnum, StatusHistory, User, WasteReport
from ..services import report_service

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _series(counter: Counter, keys: list[str]) -> list[dict]:
    return [{"label": k, "count": counter.get(k, 0)} for k in keys]


@router.get("/summary")
def summary(days: int = 30, current_user: User = Depends(require_staff), db: Session = Depends(get_db)):
    days = max(7, min(days, 365))
    reports = report_service.list_reports(db, staff_id=current_user.id) if current_user.role == RoleEnum.STAFF else report_service.waste_only(db.query(WasteReport)).all()
    now = datetime.utcnow()
    today = now.date()

    per_day = Counter(r.created_at.date().isoformat() for r in reports)
    day_keys = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
    per_week = Counter(f"{r.created_at.isocalendar().year}-W{r.created_at.isocalendar().week:02d}" for r in reports)
    week_keys = []
    for i in range(11, -1, -1):
        c = (now - timedelta(weeks=i)).isocalendar()
        week_keys.append(f"{c.year}-W{c.week:02d}")
    per_month = Counter(r.created_at.strftime("%Y-%m") for r in reports)
    month_keys, y, m = [], now.year, now.month
    for _ in range(12):
        month_keys.append(f"{y}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    month_keys.reverse()

    def top(counter, n=15):
        return [{"label": k, "count": v} for k, v in counter.most_common(n)]

    area = Counter((r.village or r.town or r.district) for r in reports if (r.village or r.town or r.district))
    ids = [r.id for r in reports]
    closed_times = []
    if ids:
        for rid, created, closed_at in (
            db.query(WasteReport.id, WasteReport.created_at, StatusHistory.created_at)
            .join(StatusHistory, StatusHistory.report_id == WasteReport.id)
            .filter(StatusHistory.new_status == "CLOSED", WasteReport.id.in_(ids)).all()
        ):
            closed_times.append((closed_at - created).total_seconds() / 3600)
    improvements = [cv.improvement_percentage for cv in db.query(CleanupVerification).filter(
        CleanupVerification.report_id.in_(ids or [-1]), CleanupVerification.improvement_percentage.isnot(None),
        CleanupVerification.verified_at.isnot(None)).all()]

    live = [r for r in reports if r.status != ReportStatus.REJECTED]
    closed = [r for r in live if r.status in (ReportStatus.CLOSED, ReportStatus.COMPLETED)]
    conf = [r.confidence for r in reports if r.confidence is not None]
    buckets = Counter("<50%" if c < .5 else "50-74%" if c < .75 else "75-89%" if c < .9 else ">=90%" for c in conf)
    hotspots = db.query(Hotspot).order_by(Hotspot.total_reports.desc()).all()

    return {
        "total_reports": len(reports),
        "reports_per_day": _series(per_day, day_keys),
        "reports_per_week": _series(per_week, week_keys),
        "reports_per_month": _series(per_month, month_keys),
        "waste_categories": top(Counter(r.waste_type or "unclassified" for r in reports)),
        "area_wise": top(area),
        "hotspot_frequency": [{"label": f"Hotspot #{h.id}", "count": h.total_reports, "severity": h.severity} for h in hotspots[:10]],
        "hotspots_total": len(hotspots),
        "cleanup_completion": {
            "eligible": len(live), "closed": len(closed),
            "rate_percent": round(100 * len(closed) / len(live), 1) if live else None,
            "awaiting_verification": sum(1 for r in live if r.status == ReportStatus.CLEANUP_VERIFICATION),
            "in_progress": sum(1 for r in live if r.status == ReportStatus.IN_PROGRESS),
        },
        "avg_resolution_hours": round(sum(closed_times) / len(closed_times), 1) if closed_times else None,
        "avg_cleanup_improvement_percent": round(sum(improvements) / len(improvements), 1) if improvements else None,
        "severity_distribution": top(Counter(r.severity for r in reports if r.severity)),
        "priority_distribution": top(Counter(r.priority.value for r in reports if r.priority)),
        "confidence_distribution": _series(buckets, ["<50%", "50-74%", "75-89%", ">=90%"]),
        "avg_confidence": round(sum(conf) / len(conf), 3) if conf else None,
    }
