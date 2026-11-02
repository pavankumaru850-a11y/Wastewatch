"""services/detection_service.py -- quality gate + detector + human
messages. Never fabricates a detection or a confidence value."""
import logging

from PIL import Image

from .. import detector
from ..config import get_settings
from . import quality_service
from .scoring_service import confidence_level

log = logging.getLogger("wastewatch.ai")

MSG_NONE = "No waste detected."
MSG_NOT_WASTE = "Not waste. This photo is saved separately and no cleanup request is created."
MSG_WASTE = "Waste detected"
# Class names a model may use for "this is NOT waste" (classifier folder / detector background class).
NON_WASTE_NAMES = {"not_waste", "non_waste", "no_waste", "notwaste", "not waste", "clean", "background"}
MSG_LOW = "Low-confidence detection. Please capture a clearer image."
MSG_UNAVAILABLE = "AI model is not currently available."


def _image_size(path: str) -> tuple[int, int] | None:
    try:
        with Image.open(path) as im:
            return im.size
    except Exception:  # noqa: BLE001
        return None


def run_detection(image_path: str, settings: dict | None = None, skip_quality: bool = False) -> dict:
    """Returns a dict with: ok, code, message, detected, detections[], object_count,
    model_version, image_size, quality. `detections` items carry both `box`
    (dict, used by the DB layer) and `bbox` ([x1,y1,x2,y2], the public API shape)."""
    settings = settings or get_settings()
    base = {"ok": True, "detected": False, "is_waste": None, "detections": [], "object_count": 0,
            "model_version": detector.active_version() or settings["model_version"], "image_size": _image_size(image_path), "quality": None}

    if not skip_quality:
        q = quality_service.check_image_quality(image_path, settings)
        base["quality"] = q
        if not q["ok"]:
            log.info("quality gate failed: %s", q["reasons"])
            return {**base, "ok": False, "code": "IMAGE_QUALITY_LOW", "message": q["message"]}

    try:
        raw = detector.predict(image_path, settings["detection_confidence"])
    except detector.ModelUnavailableError as e:
        log.warning("model unavailable: %s", e)
        return {**base, "ok": False, "code": "MODEL_UNAVAILABLE", "message": MSG_UNAVAILABLE, "detail": str(e),
                "model_version": None}
    except Exception:  # noqa: BLE001 - never leak raw exceptions to users
        log.exception("inference failed")
        return {**base, "ok": False, "code": "INFERENCE_ERROR", "message": "Something went wrong. Please try again."}

    # Binary decision: anything the model labels with a "not waste" class (or nothing at all) is NOT waste.
    non_waste = [d for d in raw if d["class_name"].strip().lower() in NON_WASTE_NAMES]
    raw = [d for d in raw if d["class_name"].strip().lower() not in NON_WASTE_NAMES]
    if not raw:
        conf = max((d["confidence"] for d in non_waste), default=None)
        return {**base, "is_waste": False, "non_waste_confidence": conf, "code": "NOT_WASTE",
                "message": MSG_NOT_WASTE if non_waste else MSG_NONE}

    dets = []
    for d in raw:
        b = d["box"]
        dets.append({**d, "bbox": [b["x1"], b["y1"], b["x2"], b["y2"]],
                     "confidence_level": confidence_level(d["confidence"])})
    best = max(d["confidence"] for d in dets)
    if confidence_level(best) == "LOW":
        code, msg = "LOW_CONFIDENCE", MSG_LOW
    else:
        code, msg = "WASTE_DETECTED", MSG_WASTE
    return {**base, "detected": True, "is_waste": True, "detections": dets, "object_count": len(dets),
            "code": code, "message": msg}


def summarize_primary_class(detections: list[dict]) -> tuple[str | None, float | None]:
    if not detections:
        return None, None
    best = max(detections, key=lambda d: d["confidence"])
    return best["class_name"], best["confidence"]


def summarize_text(detections: list[dict]) -> str | None:
    if not detections:
        return None
    from collections import Counter
    return ", ".join(f"{n}x {c}" for c, n in Counter(d["class_name"] for d in detections).most_common())[:300]
