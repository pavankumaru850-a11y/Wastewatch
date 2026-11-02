"""Reverse geocoding (GPS -> village/town/district/state/country) via OpenStreetMap Nominatim.

OPT-IN: set REVERSE_GEOCODING=true. It sends the report's coordinates to a third party, so it is
off by default. Nominatim's usage policy applies (identify your app with GEOCODER_USER_AGENT,
max ~1 request/second, no bulk use) -- for a real deployment run your own Nominatim or use a paid
provider. Failures never block a report and nothing is ever invented: on any error we return None
and the report simply has no address.
"""
import json
import logging
import os
import time
import urllib.parse
import urllib.request
from functools import lru_cache

log = logging.getLogger("wastewatch.geocode")
URL = os.environ.get("NOMINATIM_URL", "https://nominatim.openstreetmap.org/reverse")
_last_call = 0.0


def enabled() -> bool:
    return os.environ.get("REVERSE_GEOCODING", "false").lower() in ("1", "true", "yes")


def _fetch(lat: float, lng: float, timeout: float) -> dict:
    ua = os.environ.get("GEOCODER_USER_AGENT", "WasteWatch/2.0 (academic project)")
    q = urllib.parse.urlencode({"format": "jsonv2", "lat": f"{lat:.6f}", "lon": f"{lng:.6f}", "zoom": 18, "addressdetails": 1})
    req = urllib.request.Request(f"{URL}?{q}", headers={"User-Agent": ua, "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (fixed https URL)
        return json.loads(r.read().decode("utf-8"))


fetch_json = _fetch  # tests replace this


def parse(payload: dict) -> dict | None:
    a = (payload or {}).get("address")
    if not a:
        return None
    first = lambda *keys: next((a[k] for k in keys if a.get(k)), None)  # noqa: E731
    out = {
        "village": first("village", "hamlet", "suburb", "neighbourhood", "locality"),
        "town": first("town", "city", "municipality"),
        "district": first("county", "state_district", "district"),
        "state": a.get("state"),
        "country": a.get("country"),
        "address": payload.get("display_name"),
    }
    return out if any(out.values()) else None


@lru_cache(maxsize=512)
def _cached(lat4: float, lng4: float) -> tuple | None:
    global _last_call
    wait = 1.05 - (time.time() - _last_call)  # respect the 1 req/s policy
    if wait > 0:
        time.sleep(wait)
    _last_call = time.time()
    res = parse(fetch_json(lat4, lng4, 3.0))
    if res is None:
        raise LookupError("no address")  # lru_cache does not cache exceptions -> a miss is retried later
    return tuple(sorted(res.items()))


def lookup(lat: float, lng: float) -> dict | None:
    if not enabled():
        return None
    try:
        return dict(_cached(round(lat, 4), round(lng, 4)))  # ~11 m cache cells
    except Exception as e:  # noqa: BLE001 - network/timeouts/parse must never break report creation
        log.warning("reverse geocoding unavailable: %s", e)
        return None
