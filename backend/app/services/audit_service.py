"""services/audit_service.py -- the ONLY place AuditLog rows get created.
Append-only. Never store passwords/tokens in details/old/new values."""
import logging

from sqlalchemy.orm import Session

from ..models import AuditLog

log_ = logging.getLogger("wastewatch.audit")


def log(db: Session, user_id: int, action: str, report_id: int | None = None, details: str | None = None,
        old_value: str | None = None, new_value: str | None = None, ip: str | None = None) -> AuditLog:
    entry = AuditLog(user_id=user_id, action=action, report_id=report_id, details=details,
                     old_value=old_value, new_value=new_value, ip_address=ip)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    log_.info("audit user=%s action=%s report=%s", user_id, action, report_id)
    return entry


def list_logs(db: Session, report_id: int | None = None, action: str | None = None,
              user_id: int | None = None, limit: int = 200) -> list[AuditLog]:
    q = db.query(AuditLog)
    if report_id is not None:
        q = q.filter(AuditLog.report_id == report_id)
    if action:
        q = q.filter(AuditLog.action == action)
    if user_id is not None:
        q = q.filter(AuditLog.user_id == user_id)
    return q.order_by(AuditLog.created_at.desc()).limit(limit).all()
