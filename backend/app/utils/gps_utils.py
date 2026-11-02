"""utils/gps_utils.py -- validates coordinates. Reverse geocoding
(village/district/road name from lat/lng) is intentionally left to the
mobile client, which can use a device-level geocoding SDK; the backend
accepts village/district as optional submitted fields rather than
silently guessing them from coordinates alone."""
import math

from fastapi import HTTPException


def validate_coordinates(latitude: float | None, longitude: float | None):
    if latitude is None or longitude is None:
        raise HTTPException(status_code=400, detail="Location information is required.")
    if not (-90.0 <= latitude <= 90.0) or not (-180.0 <= longitude <= 180.0):
        raise HTTPException(status_code=400, detail="Location information is required.")
    return True


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lng points, in meters."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
