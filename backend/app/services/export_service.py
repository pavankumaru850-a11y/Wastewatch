"""CSV / Excel export of reports. Cells starting with = + - @ are prefixed with a
quote so a malicious description cannot become a spreadsheet formula (CSV injection)."""
import csv
import io

from openpyxl import Workbook

HEADERS = ["Report ID", "Date", "Latitude", "Longitude", "Village", "District", "Waste type", "Object count",
           "Severity", "Priority score", "Priority level", "Status", "Assigned staff", "Cleanup status",
           "Improvement %", "Hotspot ID", "Possible duplicate"]


def _safe(v):
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


def rows(db, reports):
    from ..models import CleanupVerification, StaffAssignment, User
    out = []
    for r in reports:
        a = db.query(StaffAssignment).filter(StaffAssignment.report_id == r.id).first()
        staff = db.query(User).get(a.staff_id).name if a else ""
        cv = db.query(CleanupVerification).filter(CleanupVerification.report_id == r.id).first()
        cleanup = ("Verified" if cv and cv.verified_at else "Awaiting verification") if cv and cv.after_image else ("In progress" if a else "")
        out.append([r.id, r.created_at.strftime("%Y-%m-%d %H:%M"), r.latitude, r.longitude, r.village or "", r.district or "",
                    r.waste_type or "", r.object_count or 0, r.severity or "", r.priority_score if r.priority_score is not None else "",
                    r.priority.value if r.priority else "", r.status.value, staff, cleanup,
                    cv.improvement_percentage if cv and cv.improvement_percentage is not None else "",
                    r.hotspot_id or "", "Yes" if r.is_possible_duplicate else "No"])
    return [[_safe(c) for c in row] for row in out]


def to_csv(db, reports) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(HEADERS)
    w.writerows(rows(db, reports))
    return ("\ufeff" + buf.getvalue()).encode("utf-8")  # BOM so Excel opens UTF-8 correctly


def to_xlsx(db, reports) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Reports"
    ws.append(HEADERS)
    for row in rows(db, reports):
        ws.append(row)
    ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
