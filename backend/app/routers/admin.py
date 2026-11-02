"""routers/admin.py -- everything here requires require_admin. Staff
never reach these endpoints even if they guess the URL."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..auth import require_admin, require_staff
from ..database import get_db
from ..models import User, Verification, WasteReport, ReportStatus
from ..schemas import UserOut, VerificationRequest, ReportOut, AuditLogOut
from ..services import training_service, audit_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
def list_users(role: str | None = None, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    q = db.query(User)
    if role:
        q = q.filter(User.role == role)
    return q.order_by(User.created_at.desc()).all()


@router.post("/reports/{report_id}/verify", response_model=ReportOut)
def verify_report(
    report_id: int, data: VerificationRequest, request: Request,
    current_user: User = Depends(require_staff), db: Session = Depends(get_db),
):
    """Staff/admin confirm or correct the AI classification. Goes through the
    workflow state machine (never sets status directly)."""
    from ..services import workflow_service
    from ..services.report_service import get_report_or_404
    report = get_report_or_404(db, report_id)
    if report.status not in (ReportStatus.NEW, ReportStatus.AI_DETECTED, ReportStatus.STAFF_REVIEW):
        raise HTTPException(400, f"Report is already {report.status.value}; classification can no longer be verified.")
    db.add(Verification(
        report_id=report_id, predicted_class=report.waste_type,
        verified_class=data.verified_class or report.waste_type, verified_by=current_user.id,
        verification_status=data.verification_status, remarks=data.remarks,
    ))
    ip = request.client.host if request.client else None
    if data.verification_status.value == "INCORRECT" and data.verified_class:
        old = report.waste_type
        report.waste_type = data.verified_class
        db.commit()
        audit_service.log(db, current_user.id, "CLASS_CORRECTED", report_id, None, old, data.verified_class, ip)
    if data.verification_status.value in ("CORRECT", "INCORRECT"):
        workflow_service.change_status(db, report, ReportStatus.VERIFIED, current_user, data.remarks, ip)
    else:
        db.commit()
    audit_service.log(db, current_user.id, f"VERIFY_{data.verification_status.value}", report_id, data.remarks, ip=ip)
    db.refresh(report)
    return report


@router.get("/audit-log", response_model=list[AuditLogOut])
def audit_log(report_id: int | None = None, action: str | None = None, user_id: int | None = None, limit: int = 200, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return audit_service.list_logs(db, report_id=report_id, action=action, user_id=user_id, limit=min(limit, 1000))


@router.post("/reports/{report_id}/add-to-training", status_code=201)
def add_to_training_dataset(
    report_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db),
):
    """Explicit, controlled action -- this is the ONLY way an image enters
    training_images. A raw AI prediction never lands here automatically."""
    from ..services.report_service import get_report_or_404
    report = get_report_or_404(db, report_id)
    record = training_service.add_verified_training_image(
        db, report.image_path, report.waste_type or "unclassified", None, current_user,
    )
    return {"training_image_id": record.id, "verified": record.verified}


# ------------------------------------------------------------ v2 admin APIs
import json as _json  # noqa: E402


from ..config import default_keys, get_settings, save_scoring_config, scoring_config  # noqa: E402
from ..models import ModelVersion, RoleEnum, SystemSetting  # noqa: E402
from ..schemas import AdminCreateUser, AdminUpdateUser  # noqa: E402
from ..services import notification_service, user_service  # noqa: E402
from ..schemas import RegisterRequest  # noqa: E402


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(data: AdminCreateUser, request: Request, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """The ONLY way to create STAFF/ADMIN accounts (public registration is citizen-only)."""
    reg = RegisterRequest(name=data.name, email=data.email, password=data.password, phone=data.phone,
                          village=data.village, district=data.district)
    user = user_service.register_user(db, reg, role=data.role)
    audit_service.log(db, current_user.id, "USER_CREATED", None, f"{user.email} as {user.role.value}", ip=request.client.host if request.client else None)
    return user


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: AdminUpdateUser, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(404, "User not found.")
    if user.id == current_user.id and (data.is_active is False or (data.role and data.role != RoleEnum.ADMIN)):
        raise HTTPException(400, "You cannot deactivate or demote your own account.")
    for k, v in data.model_dump(exclude_unset=True).items():
        old = getattr(user, k)
        setattr(user, k, v)
        audit_service.log(db, current_user.id, "USER_MODIFIED", None, f"user #{user.id} {k}", str(old), str(v))
    db.commit()
    db.refresh(user)
    return user


@router.get("/settings")
def get_system_settings(current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return {"settings": get_settings(db), "scoring": scoring_config()}


@router.put("/settings")
def put_system_settings(values: dict, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    unknown = set(values) - default_keys()
    if unknown:
        raise HTTPException(400, f"Unknown setting(s): {', '.join(sorted(unknown))}")
    current = get_settings(db)
    for k, v in values.items():
        if isinstance(current[k], bool) or type(v) is not type(current[k]) and not (isinstance(v, (int, float)) and isinstance(current[k], (int, float))):
            raise HTTPException(400, f"Setting '{k}' has the wrong type.")
        if isinstance(v, (int, float)) and v < 0:
            raise HTTPException(400, f"Setting '{k}' must not be negative.")
        row = db.query(SystemSetting).get(k)
        old = current[k]
        if row:
            row.value, row.updated_by = _json.dumps(v), current_user.id
        else:
            db.add(SystemSetting(key=k, value=_json.dumps(v), updated_by=current_user.id))
        audit_service.log(db, current_user.id, "SETTING_CHANGED", None, k, _json.dumps(old), _json.dumps(v))
    db.commit()
    return {"settings": get_settings(db)}


@router.put("/scoring-config")
def put_scoring(cfg: dict, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    old = scoring_config()
    for section in ("confidence_levels", "severity", "priority", "deadline_hours"):
        if section not in cfg:
            raise HTTPException(400, f"Missing section '{section}'.")
    try:
        from ..services import scoring_service
        scoring_service.compute_severity([{"class_name": "plastic", "confidence": .9, "box": {"x1": 0, "y1": 0, "x2": 1, "y2": 1}}], cfg=cfg)
        scoring_service.compute_priority([{"class_name": "plastic", "confidence": .9}], 50, cfg=cfg)
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "Scoring configuration is malformed.")
    save_scoring_config(cfg)
    audit_service.log(db, current_user.id, "SCORING_CONFIG_CHANGED", None, "severity_config.json", _json.dumps(old)[:900], _json.dumps(cfg)[:900])
    return cfg


@router.get("/models")
def list_models(current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Registry from models/model_versions.json (written by training/export.py) merged with DB activation state."""
    registry = training_service.get_model_versions()
    active = {m.version for m in db.query(ModelVersion).filter(ModelVersion.deployed == True).all()}  # noqa: E712
    return [{**m, "active": m.get("version") in active or bool(m.get("deployed"))} for m in registry]


@router.post("/models/{version}/activate")
def activate_model(version: str, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    from .. import detector
    entry = next((m for m in training_service.get_model_versions() if m.get("version") == version), None)
    if not entry:
        raise HTTPException(404, "Model version not found in registry.")
    path = training_service.resolve_model_path(entry)
    if path is None:
        raise HTTPException(400, "Model file is missing on disk; it cannot be activated.")
    if not entry.get("map50"):
        raise HTTPException(400, "This model has no recorded evaluation metrics (or mAP50 is 0); it cannot be activated.")
    previous = detector.active_version(), str(detector.MODEL_PATH)
    detector.reload_model(str(path), version)
    if not detector.is_available():
        reason = detector.unavailable_reason()
        if previous[1]:
            detector.set_active(previous[1], previous[0])  # roll back to what was serving before
        raise HTTPException(400, f"Model failed to load; it was not activated. ({reason})")
    db.query(ModelVersion).update({"deployed": False})
    mv = db.query(ModelVersion).filter(ModelVersion.version == version).first() or ModelVersion(
        model_name=entry.get("model_name", "wastewatch"), version=version, path=str(path))
    mv.path, mv.deployed = str(path), True
    mv.map50, mv.precision, mv.recall, mv.map5095 = entry.get("map50"), entry.get("precision"), entry.get("recall"), entry.get("map5095")
    mv.dataset_version = entry.get("dataset_version")
    db.add(mv)
    db.commit()
    audit_service.log(db, current_user.id, "MODEL_ACTIVATED", None, version, None, version)
    notification_service.notify_role(db, [RoleEnum.ADMIN], "AI model changed", f"Active model is now {version}", "model")
    return {"active": version}
