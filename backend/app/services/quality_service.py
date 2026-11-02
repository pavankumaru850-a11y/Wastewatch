"""Image quality gate run BEFORE detection. Deliberately lenient: it only
rejects images that are unusable (tiny, corrupt, near-black/white, very
blurry) so ordinary phone photos are never turned away."""
import numpy as np
from PIL import Image, UnidentifiedImageError

QUALITY_MESSAGE = "Image quality is too low. Please capture a clearer image."


def _laplacian_variance(gray: np.ndarray) -> float:
    g = gray.astype(np.float32)
    lap = (-4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:])
    return float(lap.var())


def check_image_quality(path: str, settings: dict) -> dict:
    """Returns {ok, reasons[], metrics{}, message}."""
    reasons: list[str] = []
    metrics: dict = {}
    try:
        with Image.open(path) as im:
            im.load()
            fmt = (im.format or "").lower()
            w, h = im.size
            gray = np.asarray(im.convert("L").resize((min(w, 640), max(1, int(h * min(w, 640) / w)))))
    except (UnidentifiedImageError, OSError):
        return {"ok": False, "reasons": ["unreadable"], "metrics": {}, "message": "The image could not be read."}

    metrics.update(width=w, height=h, format=fmt)
    if fmt not in settings["allowed_image_types"]:
        reasons.append("format")
    if min(w, h) < settings["min_image_side_px"]:
        reasons.append("resolution")
    mean = float(gray.mean())
    metrics["mean_brightness"] = round(mean, 1)
    if mean < settings["dark_mean_max"]:
        reasons.append("too_dark")
    if mean > settings["bright_mean_min"]:
        reasons.append("too_bright")
    blur = _laplacian_variance(gray) if gray.shape[0] > 2 and gray.shape[1] > 2 else 0.0
    metrics["blur_score"] = round(blur, 1)
    if blur < settings["blur_threshold"]:
        reasons.append("blurry")
    ok = not reasons
    return {"ok": ok, "reasons": reasons, "metrics": metrics, "message": None if ok else QUALITY_MESSAGE}
