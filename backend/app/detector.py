"""
detector.py -- wraps Ultralytics YOLO. Never fabricates a prediction.

If ultralytics isn't installed, or backend/models/best.pt doesn't exist
yet (nothing has been trained/deployed), predict() raises
ModelUnavailableError with a clear message instead of crashing or
returning made-up detections -- matching the spec's error-handling
requirements exactly.
"""
import os
from pathlib import Path
from threading import Lock

BACKEND_DIR = Path(__file__).resolve().parent.parent
_configured_model_path = Path(os.environ.get("MODEL_PATH", BACKEND_DIR / "models" / "best.pt"))
MODEL_PATH = (
    _configured_model_path
    if _configured_model_path.is_absolute()
    else BACKEND_DIR / _configured_model_path
)
CONFIDENCE_THRESHOLD = float(os.environ.get("WW_CONF_THRESHOLD", "0.40"))

_model = None
_model_lock = Lock()
_load_error: str | None = None


class ModelUnavailableError(Exception):
    pass


def _load_model():
    global _model, _load_error
    if _model is not None or _load_error is not None:
        return
    with _model_lock:
        if _model is not None or _load_error is not None:
            return
        if not MODEL_PATH.exists():
            _load_error = (
                f"No trained model deployed at {MODEL_PATH}. "
                "Train one with training/train.py and copy/export it there, "
                "or run training/export.py --deploy."
            )
            return
        try:
            from ultralytics import YOLO
        except ImportError:
            _load_error = "ultralytics is not installed on the server (pip install ultralytics)."
            return
        try:
            _model = YOLO(str(MODEL_PATH))
        except Exception as e:  # noqa: BLE001
            _load_error = f"Failed to load model at {MODEL_PATH}: {e}"


def is_available() -> bool:
    _load_model()
    return _model is not None


def unavailable_reason() -> str | None:
    _load_model()
    return _load_error


def predict(image_path: str, conf_threshold: float | None = None) -> list[dict]:
    """Returns a list of {class_name, confidence, box:{x1,y1,x2,y2}}.
    Raises ModelUnavailableError if no model is deployed -- callers must
    surface "AI model is not currently available." rather than pretend."""
    _load_model()
    if _model is None:
        raise ModelUnavailableError(_load_error or "AI model is not currently available.")

    threshold = conf_threshold if conf_threshold is not None else CONFIDENCE_THRESHOLD
    results = _model.predict(source=image_path, conf=threshold, verbose=False)
    detections = []
    if not results:
        return detections
    r = results[0]
    names = r.names

    # Classification model (e.g. train_classifier.py): no boxes, only class
    # probabilities. Report the top class as one whole-image "detection" so
    # the rest of the API (which expects a box) keeps working. The box is the
    # full image and does NOT locate the item.
    if getattr(_model, "task", None) == "classify" or r.probs is not None:
        top = int(r.probs.top1)
        conf = float(r.probs.top1conf)
        if conf < threshold:
            return detections
        h, w = r.orig_shape
        return [{
            "class_name": names.get(top, str(top)),
            "confidence": round(conf, 4),
            "box": {"x1": 0.0, "y1": 0.0, "x2": float(w), "y2": float(h)},
        }]

    for box in r.boxes:
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        x1, y1, x2, y2 = [float(v) for v in box.xyxy[0]]
        detections.append({
            "class_name": names.get(cls_id, str(cls_id)),
            "confidence": round(conf, 4),
            "box": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
        })
    return detections


_active_version: str | None = None


def active_version() -> str | None:
    """Version label of the model that is actually loaded/selected, or None if none was activated."""
    return _active_version


def set_active(path: str, version: str | None = None) -> None:
    """Select a model (loaded lazily on first prediction). Used at startup from the DB record."""
    global _model, _load_error, MODEL_PATH, _active_version
    with _model_lock:
        configured_path = Path(path)
        MODEL_PATH = configured_path if configured_path.is_absolute() else BACKEND_DIR / configured_path
        _model, _load_error = None, None
        _active_version = version


def reload_model(path: str, version: str | None = None) -> None:
    """Swap the active model immediately (admin activation). Caller checks is_available()."""
    set_active(path, version)
    _load_model()
