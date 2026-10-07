import threading
import time

import httpx

from app.config import settings

WFS_URL = "https://api.vworld.kr/req/wfs"
SIGUNGU_LAYER = "lt_c_adsigg_info"
CACHE_SECONDS = 24 * 60 * 60

_cache_lock = threading.Lock()
_cached_boundaries: dict | None = None
_cache_expires_at = 0.0


class VWorldError(RuntimeError):
    pass


def fetch_sigungu_boundaries() -> dict:
    """Fetch national city/county/district GeoJSON, keeping the key server-side."""
    if not settings.vworld_api_key:
        raise VWorldError("V-World WFS API key is not configured")

    params = {
        "service": "WFS",
        "request": "GetFeature",
        "version": "1.1.0",
        "typename": SIGUNGU_LAYER,
        "output": "application/json",
        "maxfeatures": "1000",
        "srsname": "EPSG:4326",
        "key": settings.vworld_api_key.get_secret_value(),
        "domain": settings.vworld_domain,
    }
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            response = client.get(WFS_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise VWorldError("V-World boundary request failed") from exc

    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        # Don't expose the upstream URL or its query string, which includes the key.
        raise VWorldError("V-World did not return a GeoJSON FeatureCollection")
    if not isinstance(payload.get("features"), list):
        raise VWorldError("V-World returned malformed boundary data")
    return payload


def get_sigungu_boundaries() -> dict:
    global _cached_boundaries, _cache_expires_at
    now = time.monotonic()
    if _cached_boundaries is not None and now < _cache_expires_at:
        return _cached_boundaries
    with _cache_lock:
        now = time.monotonic()
        if _cached_boundaries is None or now >= _cache_expires_at:
            _cached_boundaries = fetch_sigungu_boundaries()
            _cache_expires_at = time.monotonic() + CACHE_SECONDS
        return _cached_boundaries


def clear_boundary_cache() -> None:
    global _cached_boundaries, _cache_expires_at
    with _cache_lock:
        _cached_boundaries = None
        _cache_expires_at = 0.0
