"""routers/training.py -- exposes model_versions.json (written by
training/export.py) to the admin dashboard, and the verified-image
intake queue. Does not run training itself -- that happens by running
training/train.py as a separate process, on purpose (a web request
should not kick off an unbounded-length GPU job)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import User
from ..services import training_service

router = APIRouter(prefix="/api/training", tags=["training"])


@router.get("/model")
def current_model(current_user: User = Depends(require_admin)):
    model = training_service.get_current_deployed_model()
    if not model:
        return {"deployed": False, "message": "No model has been trained and deployed yet."}
    return {"deployed": True, **model}


@router.get("/model/history")
def model_history(current_user: User = Depends(require_admin)):
    return training_service.get_model_versions()


@router.get("/dataset")
def dataset_summary(current_user: User = Depends(require_admin)):
    return training_service.get_dataset_summary()


@router.get("/images")
def verified_training_images(current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    images = training_service.list_verified_training_images(db)
    return [
        {"id": i.id, "image_path": i.image_path, "class_name": i.class_name, "verified": i.verified}
        for i in images
    ]
