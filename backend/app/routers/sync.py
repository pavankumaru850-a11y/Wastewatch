"""routers/sync.py -- lets the mobile app ask which of its queued reports the server already has."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User, WasteReport

router = APIRouter(prefix="/api/sync", tags=["sync"])


class SyncStatusRequest(BaseModel):
    client_uuids: list[str] = Field(max_length=200)


@router.post("/status")
def sync_status(data: SyncStatusRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """{synced: {client_uuid: report_id}, unknown: [client_uuid]} -- only the caller's own reports are visible."""
    rows = db.query(WasteReport.client_uuid, WasteReport.id).filter(
        WasteReport.user_id == current_user.id, WasteReport.client_uuid.in_(data.client_uuids)).all()
    synced = {u: i for u, i in rows}
    return {"synced": synced, "unknown": [u for u in data.client_uuids if u not in synced]}
