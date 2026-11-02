"""services/notification_service.py -- in-app notifications stored in the
DB (clients poll GET /api/notifications). Also keeps the original
reports_since / assignments_since_for_staff helpers used by the dashboard."""
from datetime import datetime

from sqlalchemy.orm import Session

from ..models import Notification, RoleEnum, User, WasteReport


def notify(db: Session, user_id: int, title: str, body: str | None = None,
           kind: str | None = None, report_id: int | None = None) -> Notification:
    n = Notification(user_id=user_id, title=title, body=body, kind=kind, report_id=report_id)
    db.add(n)
    db.commit()
    return n


def notify_role(db: Session, roles: list[RoleEnum], title: str, body: str | None = None,
                kind: str | None = None, report_id: int | None = None) -> int:
    users = db.query(User).filter(User.role.in_(roles), User.is_active == True).all()  # noqa: E712
    for u in users:
        db.add(Notification(user_id=u.id, title=title, body=body, kind=kind, report_id=report_id))
    db.commit()
    return len(users)


def reports_since(db: Session, since: datetime) -> list[WasteReport]:
    from ..models import ReportStatus
    return (db.query(WasteReport).filter(WasteReport.created_at > since, WasteReport.status != ReportStatus.NOT_WASTE)
            .order_by(WasteReport.created_at.desc()).all())


def assignments_since_for_staff(db: Session, staff_id: int, since: datetime):
    from ..models import StaffAssignment
    return (db.query(StaffAssignment)
            .filter(StaffAssignment.staff_id == staff_id, StaffAssignment.assigned_at > since)
            .order_by(StaffAssignment.assigned_at.desc()).all())
