"""routers/waste_types.py -- admin-configurable waste classes. Any
authenticated user can list them (mobile app + dashboard both need the
list for dropdowns); only admin can add or deactivate one."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_admin
from ..database import get_db
from ..models import WasteType, User
from ..schemas import WasteTypeOut, WasteTypeCreate

router = APIRouter(prefix="/api/waste-types", tags=["waste-types"])


@router.get("", response_model=list[WasteTypeOut])
def list_waste_types(
    active_only: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(WasteType)
    if active_only:
        q = q.filter(WasteType.is_active == True)  # noqa: E712
    return q.order_by(WasteType.id).all()


@router.post("", response_model=WasteTypeOut, status_code=201)
def create_waste_type(
    data: WasteTypeCreate, current_user: User = Depends(require_admin), db: Session = Depends(get_db),
):
    name = data.name.strip().lower().replace(" ", "_")
    existing = db.query(WasteType).filter(WasteType.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="A waste type with this name already exists.")
    wt = WasteType(name=name, label=data.label or name.replace("_", " ").title(), is_active=True)
    db.add(wt)
    db.commit()
    db.refresh(wt)
    return wt


@router.put("/{waste_type_id}/deactivate", response_model=WasteTypeOut)
def deactivate_waste_type(
    waste_type_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db),
):
    wt = db.query(WasteType).filter(WasteType.id == waste_type_id).first()
    if not wt:
        raise HTTPException(status_code=404, detail="Waste type not found.")
    wt.is_active = False
    db.commit()
    db.refresh(wt)
    return wt


@router.put("/{waste_type_id}/activate", response_model=WasteTypeOut)
def activate_waste_type(
    waste_type_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db),
):
    wt = db.query(WasteType).filter(WasteType.id == waste_type_id).first()
    if not wt:
        raise HTTPException(status_code=404, detail="Waste type not found.")
    wt.is_active = True
    db.commit()
    db.refresh(wt)
    return wt
