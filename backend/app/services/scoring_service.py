"""Severity + priority + confidence engines. All numbers come from
config/severity_config.json (see docs). Pure functions: easy to unit-test."""
from ..config import scoring_config

SEVERITY_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def confidence_level(conf: float | None, cfg: dict | None = None) -> str | None:
    if conf is None:
        return None
    lv = (cfg or scoring_config())["confidence_levels"]
    if conf >= lv["high_min"]:
        return "HIGH"
    if conf >= lv["medium_min"]:
        return "MEDIUM"
    return "LOW"


def _level(score: float, thresholds: dict) -> str:
    level = "LOW"
    for name in ("MEDIUM", "HIGH", "CRITICAL"):
        if score >= thresholds[name]:
            level = name
    return level


def _area_fraction(detections: list[dict], img_w: float | None, img_h: float | None) -> float:
    if not detections or not img_w or not img_h:
        return 0.0
    total = 0.0
    for d in detections:
        b = d["box"]
        total += max(0.0, b["x2"] - b["x1"]) * max(0.0, b["y2"] - b["y1"])
    return min(total / (img_w * img_h), 1.0)  # overlaps can exceed 1; cap it


def compute_severity(detections: list[dict], repeat_count: int = 0, in_hotspot: bool = False,
                     img_size: tuple[float, float] | None = None, cfg: dict | None = None) -> dict:
    """Returns {score(0-100), level, breakdown{}}. Empty detections -> score 0, LOW."""
    cfg = cfg or scoring_config()
    s = cfg["severity"]
    n = len(detections)
    if n == 0:
        return {"score": 0.0, "level": "LOW", "breakdown": {}}
    count_pts = 0
    for min_n, pts in s["object_count_points"]:
        if n >= min_n:
            count_pts = pts
    class_pts = max(s["class_points"].get(d["class_name"], s["default_class_points"]) for d in detections)
    area_pts = _area_fraction(detections, *(img_size or (None, None))) * s["area_points_per_full_frame"]
    avg_conf = sum(d["confidence"] for d in detections) / n
    conf_pts = avg_conf * s["confidence_points_max"]
    repeat_pts = min(repeat_count * s["repeat_report_points_each"], s["repeat_report_points_max"])
    hotspot_pts = s["hotspot_points"] if in_hotspot else 0
    breakdown = {"object_count": count_pts, "class": class_pts, "area": round(area_pts, 1),
                 "confidence": round(conf_pts, 1), "repeat": repeat_pts, "hotspot": hotspot_pts}
    score = round(min(sum(breakdown.values()), 100.0), 1)
    return {"score": score, "level": _level(score, s["levels"]), "breakdown": breakdown}


def compute_priority(detections: list[dict], severity_score: float, repeat_count: int = 0,
                     hotspot_reports: int = 0, cfg: dict | None = None) -> dict:
    """Returns {score(0-100), level}. Weighted sum of normalised 0-1 factors."""
    cfg = cfg or scoring_config()
    p = cfg["priority"]
    w = p["weights"]
    n = len(detections)
    if n == 0:
        return {"score": 0.0, "level": "LOW"}
    factors = {
        "quantity": min(n / p["quantity_full_at_objects"], 1.0),
        "severity": min(severity_score / 100.0, 1.0),
        "repeat": min(repeat_count / p["repeat_full_at_reports"], 1.0),
        "hotspot": min(hotspot_reports / p["hotspot_full_at_reports"], 1.0),
        "drainage": 1.0 if any(d["class_name"] == "drainage_waste" for d in detections) else 0.0,
        "confidence": sum(d["confidence"] for d in detections) / n,
    }
    score = round(100 * sum(w[k] * v for k, v in factors.items()), 1)
    return {"score": score, "level": _level(score, p["levels"])}
