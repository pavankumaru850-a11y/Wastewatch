"""routers/dashboard.py -- GET /api/dashboard/stats for the summary cards,
GET /api/dashboard/recent for polling-based "new report" notifications
(polling every 5s, as the spec explicitly allows for a first
implementation -- no invented WebSocket)."""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User, WasteReport, ReportStatus, PriorityEnum, RoleEnum
from ..schemas import DashboardStats
from ..services import notification_service, report_service

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    base = report_service.waste_only(db.query(WasteReport))
    if current_user.role == RoleEnum.CITIZEN:
        base = base.filter(WasteReport.user_id == current_user.id)
    elif current_user.role == RoleEnum.STAFF:
        from ..models import StaffAssignment
        base = base.join(StaffAssignment).filter(StaffAssignment.staff_id == current_user.id)

    def count(**kwargs):
        q = base
        for k, v in kwargs.items():
            q = q.filter(getattr(WasteReport, k) == v)
        return q.count()

    return DashboardStats(
        total_reports=base.count(),
        new=count(status=ReportStatus.NEW),
        verified=count(status=ReportStatus.VERIFIED),
        assigned=count(status=ReportStatus.ASSIGNED),
        in_progress=count(status=ReportStatus.IN_PROGRESS),
        completed=count(status=ReportStatus.COMPLETED),
        rejected=count(status=ReportStatus.REJECTED),
        critical=count(priority=PriorityEnum.CRITICAL),
    )


@router.get("/recent")
def recent(since: datetime = Query(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    reports = notification_service.reports_since(db, since)
    return {"count": len(reports), "reports": [r.id for r in reports], "server_time": datetime.utcnow()}


@router.get("/analytics")
def analytics(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Real aggregations over waste_reports/completion_reports -- nothing
    here is a placeholder chart with invented numbers."""
    from sqlalchemy import func
    from ..models import CompletionReport

    base = report_service.waste_only(db.query(WasteReport))
    if current_user.role == RoleEnum.CITIZEN:
        base = base.filter(WasteReport.user_id == current_user.id)
    elif current_user.role == RoleEnum.STAFF:
        from ..models import StaffAssignment
        base = base.join(StaffAssignment).filter(StaffAssignment.staff_id == current_user.id)
    ids_subq = [r.id for r in base.all()]

    def group_count(column):
        q = (
            db.query(column, func.count(WasteReport.id))
            .filter(WasteReport.id.in_(ids_subq))
            .group_by(column)
        )
        return {(k.value if hasattr(k, "value") else str(k)): v for k, v in q.all() if k is not None}

    by_status = group_count(WasteReport.status)
    by_priority = group_count(WasteReport.priority)
    by_waste_type = group_count(WasteReport.waste_type)
    by_village = group_count(WasteReport.village)
    from collections import Counter
    by_month = dict(Counter(d.strftime("%Y-%m") for (d,) in db.query(WasteReport.created_at).filter(WasteReport.id.in_(ids_subq)).all()))

    completed = (
        db.query(WasteReport.created_at, CompletionReport.completed_at)
        .join(CompletionReport, CompletionReport.report_id == WasteReport.id)
        .filter(WasteReport.id.in_(ids_subq))
        .all()
    )
    if completed:
        hours = [(c[1] - c[0]).total_seconds() / 3600 for c in completed]
        avg_resolution_hours = round(sum(hours) / len(hours), 2)
    else:
        avg_resolution_hours = None

    confidences = [
        c[0] for c in db.query(WasteReport.confidence)
        .filter(WasteReport.id.in_(ids_subq), WasteReport.confidence.isnot(None)).all()
    ]
    buckets = {"<0.5": 0, "0.5-0.7": 0, "0.7-0.9": 0, ">=0.9": 0}
    for c in confidences:
        if c < 0.5:
            buckets["<0.5"] += 1
        elif c < 0.7:
            buckets["0.5-0.7"] += 1
        elif c < 0.9:
            buckets["0.7-0.9"] += 1
        else:
            buckets[">=0.9"] += 1

    return {
        "by_status": by_status,
        "by_priority": by_priority,
        "by_waste_type": by_waste_type,
        "by_village": by_village,
        "by_month": by_month,
        "avg_resolution_hours": avg_resolution_hours,
        "confidence_distribution": buckets,
        "sample_size": len(ids_subq),
    }


@router.get("/hotspots")
def hotspots(min_reports: int = Query(2, ge=1), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Groups reports into ~500m grid cells (rounding lat/lng to 3
    decimal places) and returns cells with repeat reports -- a simple,
    honest proxy for 'this spot keeps getting dirty' without needing a
    geospatial database extension."""
    from collections import defaultdict

    base = report_service.waste_only(db.query(WasteReport))
    if current_user.role == RoleEnum.CITIZEN:
        base = base.filter(WasteReport.user_id == current_user.id)
    elif current_user.role == RoleEnum.STAFF:
        from ..models import StaffAssignment
        base = base.join(StaffAssignment).filter(StaffAssignment.staff_id == current_user.id)

    cells = defaultdict(list)
    for r in base.all():
        key = (round(r.latitude, 3), round(r.longitude, 3))
        cells[key].append(r)

    result = []
    for (lat, lng), reports in cells.items():
        if len(reports) < min_reports:
            continue
        open_count = sum(1 for r in reports if r.status.value not in ("COMPLETED", "REJECTED"))
        types = defaultdict(int)
        for r in reports:
            if r.waste_type:
                types[r.waste_type] += 1
        dominant_type = max(types, key=types.get) if types else None
        result.append({
            "latitude": lat, "longitude": lng, "report_count": len(reports),
            "open_count": open_count, "dominant_waste_type": dominant_type,
            "village": reports[0].village, "district": reports[0].district,
            "last_reported_at": max(r.created_at for r in reports),
        })
    result.sort(key=lambda c: c["report_count"], reverse=True)
    return result


@router.get("/cleanliness-score")
def cleanliness_score(by: str = Query("village", pattern="^(village|district)$"), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Score per village/district = share of reports resolved
    (COMPLETED) out of all non-rejected reports there. 100 = fully
    clean/resolved, 0 = nothing resolved yet. Areas with no reports at
    all are not returned -- there's no data to score them on."""
    from collections import defaultdict

    base = report_service.waste_only(db.query(WasteReport))
    if current_user.role == RoleEnum.CITIZEN:
        base = base.filter(WasteReport.user_id == current_user.id)
    elif current_user.role == RoleEnum.STAFF:
        from ..models import StaffAssignment
        base = base.join(StaffAssignment).filter(StaffAssignment.staff_id == current_user.id)

    groups = defaultdict(lambda: {"total": 0, "completed": 0})
    for r in base.all():
        key = getattr(r, by)
        if not key:
            continue
        if r.status == ReportStatus.REJECTED:
            continue
        groups[key]["total"] += 1
        if r.status == ReportStatus.COMPLETED:
            groups[key]["completed"] += 1

    result = [
        {
            "area": key, "score": round(100 * v["completed"] / v["total"]) if v["total"] else None,
            "total_reports": v["total"], "completed": v["completed"],
        }
        for key, v in groups.items()
    ]
    result.sort(key=lambda x: (x["score"] is None, x["score"] or 0))
    return result


@router.get("/cards")
def cards(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Admin/staff summary cards. Every number is a live query."""
    from datetime import timedelta
    from sqlalchemy import func
    from ..auth import require_staff  # noqa: F401
    from ..models import CleanupVerification, Hotspot, StatusHistory
    from fastapi import HTTPException
    if current_user.role == RoleEnum.CITIZEN:
        raise HTTPException(status_code=403, detail="You do not have permission to perform this action.")
    R = WasteReport
    base = report_service.waste_only(db.query(R))
    if current_user.role == RoleEnum.STAFF:
        from ..services.report_service import REVIEW_QUEUE
        from ..models import StaffAssignment
        ids = [r.id for r in report_service.list_reports(db, staff_id=current_user.id)]
        base = base.filter(R.id.in_(ids)) if ids else base.filter(R.id == -1)
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    closed = db.query(R.created_at, StatusHistory.created_at).join(StatusHistory, StatusHistory.report_id == R.id).filter(StatusHistory.new_status == "CLOSED").all()
    hours = [(c - r).total_seconds() / 3600 for r, c in closed]
    open_states = [ReportStatus.NEW, ReportStatus.AI_DETECTED, ReportStatus.STAFF_REVIEW]
    return {
        "total_reports": base.count(),
        "todays_reports": base.filter(R.created_at >= today).count(),
        "pending_verification": base.filter(R.status.in_(open_states)).count(),
        "high_priority": base.filter(R.priority == PriorityEnum.HIGH).count(),
        "critical_reports": base.filter(R.priority == PriorityEnum.CRITICAL).count(),
        "active_hotspots": db.query(Hotspot).filter(Hotspot.current_status == "ACTIVE").count(),
        "completed_cleanups": base.filter(R.status == ReportStatus.CLOSED).count(),
        "awaiting_cleanup_verification": base.filter(R.status == ReportStatus.CLEANUP_VERIFICATION).count(),
        "possible_duplicates": base.filter(R.is_possible_duplicate == True).count(),  # noqa: E712
        "avg_resolution_hours": round(sum(hours) / len(hours), 1) if hours else None,
        # photos the AI judged "not waste": stored separately, never part of the totals above
        "not_waste_reports": db.query(R).filter(R.status == ReportStatus.NOT_WASTE).count() if current_user.role == RoleEnum.ADMIN else 0,
    }
