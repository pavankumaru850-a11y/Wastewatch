"""routers/detection.py -- POST /api/detection/predict: preview AI result
(quality gate, boxes, confidence, severity, priority) without saving a report."""
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import get_settings
from ..database import get_db
from ..models import User
from ..schemas import DetectionResponse
from ..services import detection_service, scoring_service
from ..utils.file_utils import physical_path, save_upload

router = APIRouter(prefix="/api/detection", tags=["detection"])


@router.post("/predict", response_model=DetectionResponse)
def predict(image: UploadFile = File(...), latitude: Optional[float] = Form(None),
            longitude: Optional[float] = Form(None), current_user: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    settings = get_settings(db)
    path = physical_path(save_upload(image, settings))
    r = detection_service.run_detection(path, settings)
    dets = r["detections"]
    conf = max((d["confidence"] for d in dets), default=None)
    sev = scoring_service.compute_severity(dets, img_size=r.get("image_size")) if dets else None
    pri = scoring_service.compute_priority(dets, sev["score"]) if sev else None
    return DetectionResponse(
        success=r["ok"], detected=r["detected"], is_waste=r.get("is_waste"), code=r.get("code"), message=r.get("message"),
        detections=dets, object_count=r["object_count"], model_version=r["model_version"],
        confidence_level=scoring_service.confidence_level(conf),
        severity=sev["level"] if sev else None, severity_score=sev["score"] if sev else None,
        priority_score=pri["score"] if pri else None, priority_level=pri["level"] if pri else None,
        quality=r.get("quality"))
