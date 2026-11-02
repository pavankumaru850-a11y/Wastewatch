"""services/pdf_service.py -- builds a municipal summary PDF from real
WasteReport rows (whatever list_reports() returns for the given
filters). Nothing here is a mock-up; every row and every count comes
straight from the database at request time."""
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from ..models import WasteReport


def build_report_pdf(reports: list[WasteReport], filters: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("WasteWatch -- Waste Report Summary", styles["Title"]))
    story.append(Paragraph(f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", styles["Normal"]))
    active_filters = ", ".join(f"{k}={v}" for k, v in filters.items() if v) or "none"
    story.append(Paragraph(f"Filters: {active_filters}", styles["Normal"]))
    story.append(Paragraph(f"Total reports: {len(reports)}", styles["Normal"]))
    story.append(Spacer(1, 8 * mm))

    header = ["ID", "Waste Type", "Priority", "Status", "Village", "District", "Reported"]
    rows = [header]
    for r in reports:
        rows.append([
            f"WW-{r.id:06d}", r.waste_type or "Unclassified", r.priority.value, r.status.value,
            r.village or "-", r.district or "-", r.created_at.strftime("%Y-%m-%d"),
        ])

    table = Table(rows, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f7a4d")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
    ]))
    story.append(table)

    doc.build(story)
    return buf.getvalue()
