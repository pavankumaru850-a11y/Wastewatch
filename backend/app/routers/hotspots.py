"""routers/hotspots.py -- clustered hotspots (staff/admin)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_staff
from ..database import get_db
from ..models import Hotspot, User
from ..schemas import HotspotOut
from ..services import hotspot_service

router = APIRouter(prefix="/api/hotspots", tags=["hotspots"])


def _out(h: Hotspot) -> HotspotOut:
    o = HotspotOut.model_validate(h)
    o.color = hotspot_service.hotspot_color(h.severity)
    return o


@router.get("", response_model=list[HotspotOut])
def list_hotspots(status: str | None = None, current_user: User = Depends(require_staff), db: Session = Depends(get_db)):
    q = db.query(Hotspot)
    if status:
        q = q.filter(Hotspot.current_status == status)
    return [_out(h) for h in q.order_by(Hotspot.priority_score.desc()).all()]


@router.get("/{hotspot_id}/history")
def history(hotspot_id: int, current_user: User = Depends(require_staff), db: Session = Depends(get_db)):
    h = db.query(Hotspot).get(hotspot_id)
    if not h:
        raise HTTPException(404, "Hotspot not found.")
    return {"hotspot": _out(h), "timeline": hotspot_service.hotspot_history(db, hotspot_id)}
