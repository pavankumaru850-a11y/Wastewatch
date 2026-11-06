"""services/training_service.py -- bridges the backend to the separate
training/ pipeline (train.py / export.py). The backend does not train
models itself; it reads the model_versions.json registry that
training/export.py writes, and manages which verified images/labels are
queued for the next retrain. Nothing here is added to the training set
automatically -- only via explicit admin/staff verification."""
import json
import os
from pathlib import Path

from sqlalchemy.orm import Session

from ..models import TrainingImage, User

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = Path(os.environ.get("WW_REPO_ROOT") or BACKEND_DIR.parent)
MODEL_VERSIONS_FILE = Path(os.environ.get("MODEL_REGISTRY") or BACKEND_DIR / "models" / "model_versions.json")
TRAINING_DATA_DIR = Path(os.environ.get("WW_TRAINING_DATA_DIR") or REPO_ROOT / "training")
IMAGE_EXTENSIONS = {".bmp", ".jpeg", ".jpg", ".png", ".webp"}


def resolve_model_path(entry: dict) -> Path | None:
    """training/export.py writes paths relative to the REPO root ('backend/models/wastewatch_v1/best.pt').
    Also accept absolute paths and paths relative to backend/. Returns the first that exists, else None."""
    raw = Path(entry.get("path", ""))
    if not str(raw):
        return None
    if raw.is_absolute():
        candidates = [raw]
    else:
        candidates = [REPO_ROOT / raw, BACKEND_DIR / raw]
        if raw.parts and raw.parts[0] == "backend":          # container layout: only backend/ is mounted at /app
            candidates.append(BACKEND_DIR.joinpath(*raw.parts[1:]))
    return next((c for c in candidates if c.exists()), None)


def get_model_versions() -> list[dict]:
    if not MODEL_VERSIONS_FILE.exists():
        return []
    return json.loads(MODEL_VERSIONS_FILE.read_text())


def get_current_deployed_model() -> dict | None:
    versions = get_model_versions()
    deployed = [v for v in versions if v.get("deployed")]
    return deployed[-1] if deployed else None


def _count_dataset_classes(directory: Path) -> dict[str, int]:
    if not directory.is_dir():
        return {}
    return {
        class_dir.name: sum(
            1 for image in class_dir.rglob("*")
            if image.is_file() and image.suffix.lower() in IMAGE_EXTENSIONS
        )
        for class_dir in sorted(directory.iterdir())
        if class_dir.is_dir()
    }


def _dataset_counts(directory: Path) -> dict:
    classes = _count_dataset_classes(directory)
    return {"classes": classes, "total": sum(classes.values())}


def get_dataset_summary() -> dict:
    combined_dir = TRAINING_DATA_DIR / "dataset_binary_combined"
    split_dir = TRAINING_DATA_DIR / "dataset_cls"
    return {
        "available": combined_dir.is_dir() or split_dir.is_dir(),
        "source": _dataset_counts(combined_dir),
        "splits": {
            split: _dataset_counts(split_dir / split)
            for split in ("train", "val", "test")
        },
    }


def add_verified_training_image(
    db: Session, image_path: str, class_name: str, annotation_path: str | None,
    uploaded_by: User,
) -> TrainingImage:
    """Only called from an explicit Admin/Staff 'Add to Training Dataset'
    action (see routers/training.py) -- never automatically after a raw
    AI prediction."""
    record = TrainingImage(
        image_path=image_path,
        class_name=class_name,
        annotation_path=annotation_path,
        verified=True,
        uploaded_by=uploaded_by.id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_verified_training_images(db: Session) -> list[TrainingImage]:
    return db.query(TrainingImage).filter(TrainingImage.verified == True).all()  # noqa: E712
