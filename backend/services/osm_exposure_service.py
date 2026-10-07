"""Small, cached Overpass lookups for estimated nearby public infrastructure.

Only an Admin-triggered complaint inspection/map click requests OSM data. Results
are cached by a rounded location cell and radius; raw Overpass payloads are not
persisted. Public Overpass failures are returned as an unavailable state, never
as a request failure for the existing complaint workflow.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import socket
import time
from datetime import datetime, timedelta, timezone
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from .. import models

DEFAULT_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
CACHE_CELL_DECIMALS = 3
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
USER_AGENT = "CityLensAI/1.0 (estimated public-infrastructure exposure)"


def _int_setting(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        return min(max(int(os.getenv(name, str(default))), minimum), maximum)
    except (TypeError, ValueError):
        return default


def _float_setting(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        return min(max(float(os.getenv(name, str(default))), minimum), maximum)
    except (TypeError, ValueError):
        return default


def configured_radius_m() -> int:
    return _int_setting("CITYLENS_IMPACT_RADIUS_METERS", 500, 100, 2000)


def configured_timeout_seconds() -> int:
    return _int_setting("CITYLENS_OVERPASS_TIMEOUT_SECONDS", 10, 3, 30)


def _cache_ttl_seconds(source_status: str) -> int:
    if source_status == "available":
        return _int_setting("CITYLENS_IMPACT_CACHE_DAYS", 30, 1, 365) * 86400
    return _int_setting("CITYLENS_IMPACT_FAILURE_CACHE_SECONDS", 900, 60, 3600)


def _valid_coordinates(latitude: float, longitude: float) -> bool:
    return (
        isinstance(latitude, (int, float))
        and isinstance(longitude, (int, float))
        and math.isfinite(latitude)
        and math.isfinite(longitude)
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    )


def _cache_location(latitude: float, longitude: float, radius_m: int):
    # Queries are snapped to a ~100 m cell so nearby reports reuse one result.
    cell_lat = round(float(latitude), CACHE_CELL_DECIMALS)
    cell_lon = round(float(longitude), CACHE_CELL_DECIMALS)
    key = f"osm-v1:{cell_lat:.3f}:{cell_lon:.3f}:{radius_m}"
    return key, cell_lat, cell_lon


def build_overpass_query(latitude: float, longitude: float, radius_m: int, timeout_seconds: int) -> str:
    """Return one bounded query for all requested features around a snapped cell."""
    lat = f"{latitude:.6f}"
    lon = f"{longitude:.6f}"
    return f"""[out:json][timeout:{timeout_seconds}];
(
  nwr(around:{radius_m},{lat},{lon})[\"amenity\"~\"^(school|kindergarten|college|university|hospital|clinic)$\"];
  nwr(around:{radius_m},{lat},{lon})[\"healthcare\"~\"^(hospital|clinic)$\"];
  nwr(around:{radius_m},{lat},{lon})[\"highway\"=\"bus_stop\"];
  nwr(around:{radius_m},{lat},{lon})[\"public_transport\"~\"^(platform|stop_position)$\"];
  way(around:{radius_m},{lat},{lon})[\"highway\"~\"^(motorway|trunk|primary|secondary)$\"];
);
out center tags;"""


def _count_features(document: dict) -> dict[str, int]:
    elements = document.get("elements")
    if not isinstance(elements, list):
        raise ValueError("Overpass response has no elements array")
    buckets = {name: set() for name in ("schools", "hospitals", "clinics", "bus_stops", "major_roads")}
    for element in elements:
        if not isinstance(element, dict):
            continue
        tags = element.get("tags") or {}
        if not isinstance(tags, dict):
            continue
        object_key = (element.get("type"), element.get("id"))
        amenity = tags.get("amenity", "").lower()
        healthcare = tags.get("healthcare", "").lower()
        if amenity in {"school", "kindergarten", "college", "university"}:
            buckets["schools"].add(object_key)
        if amenity == "hospital" or healthcare == "hospital":
            buckets["hospitals"].add(object_key)
        if amenity == "clinic" or healthcare == "clinic":
            buckets["clinics"].add(object_key)
        if tags.get("highway") == "bus_stop" or tags.get("public_transport") in {"platform", "stop_position"}:
            buckets["bus_stops"].add(object_key)
        if tags.get("highway") in {"motorway", "trunk", "primary", "secondary"}:
            buckets["major_roads"].add(object_key)
    return {name: len(values) for name, values in buckets.items()}


def _http_overpass(url: str, query: str, timeout_seconds: int) -> dict:
    request = Request(
        url,
        data=urlencode({"data": query}).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": USER_AGENT},
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("Overpass response exceeded the local safety limit")
    document = json.loads(raw.decode("utf-8"))
    if not isinstance(document, dict):
        raise ValueError("Overpass response is not a JSON object")
    return _count_features(document)


def _error_code(exc: Exception) -> str:
    if isinstance(exc, HTTPError):
        if exc.code == 429:
            return "rate_limited"
        if exc.code in {502, 503, 504}:
            return "service_unavailable"
        return "http_error"
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(exc, URLError):
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            return "timeout"
        return "network_error"
    if isinstance(exc, json.JSONDecodeError):
        return "invalid_response"
    return "invalid_response"


_RATE_LOCK = asyncio.Lock()
_LAST_REQUEST_AT = 0.0
_CELL_LOCKS: dict[str, asyncio.Lock] = {}
_CELL_LOCKS_GUARD = Lock()


def _cell_lock(cache_key: str) -> asyncio.Lock:
    with _CELL_LOCKS_GUARD:
        return _CELL_LOCKS.setdefault(cache_key, asyncio.Lock())


async def _wait_for_public_api_slot() -> None:
    global _LAST_REQUEST_AT
    minimum_interval = _float_setting("CITYLENS_OVERPASS_MIN_INTERVAL_SECONDS", 1.5, 0.5, 30.0)
    async with _RATE_LOCK:
        delay = minimum_interval - (time.monotonic() - _LAST_REQUEST_AT)
        if delay > 0:
            await asyncio.sleep(delay)
        _LAST_REQUEST_AT = time.monotonic()


def _aware_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _fresh_cache(db: Session, cache_key: str):
    record = db.query(models.OSMExposureCache).filter_by(cache_key=cache_key).first()
    if record is None:
        return None
    fetched_at = _aware_utc(record.fetched_at)
    if datetime.now(timezone.utc) - fetched_at >= timedelta(seconds=_cache_ttl_seconds(record.source_status)):
        return None
    try:
        counts = json.loads(record.counts_json)
        if not isinstance(counts, dict):
            return None
    except (TypeError, json.JSONDecodeError):
        return None
    return {
        "status": record.source_status,
        "counts": counts if record.source_status == "available" else None,
        "error_code": record.error_code,
        "fetched_at": fetched_at.isoformat(),
        "cache_hit": True,
    }


def _persist_cache(db: Session, cache_key: str, latitude: float, longitude: float, radius_m: int, status: str, counts: dict, error_code: str | None, fetched_at: datetime) -> None:
    record = db.query(models.OSMExposureCache).filter_by(cache_key=cache_key).first()
    if record is None:
        record = models.OSMExposureCache(cache_key=cache_key)
        db.add(record)
    record.latitude_cell = latitude
    record.longitude_cell = longitude
    record.radius_m = radius_m
    record.source_status = status
    record.counts_json = json.dumps(counts, separators=(",", ":"))
    record.error_code = error_code
    record.fetched_at = fetched_at
    try:
        db.commit()
    except Exception:
        # A cache-write problem must not turn otherwise valid complaint work into a 500.
        db.rollback()


async def get_nearby_exposure(db: Session, latitude: float, longitude: float) -> dict:
    radius_m = configured_radius_m()
    if not _valid_coordinates(latitude, longitude):
        return {
            "status": "invalid_coordinates", "counts": None, "error_code": "invalid_coordinates",
            "fetched_at": None, "cache_hit": False, "radius_m": radius_m,
        }

    cache_key, cell_lat, cell_lon = _cache_location(latitude, longitude, radius_m)
    async with _cell_lock(cache_key):
        cached = _fresh_cache(db, cache_key)
        if cached is not None:
            return {**cached, "radius_m": radius_m}

        # Cache misses are read-only here. End the lookup/recurrence read
        # transaction before any queue/network wait so SQLite complaint writes
        # are not held behind a slow public API response.
        db.rollback()
        url = os.getenv("CITYLENS_OVERPASS_URL", DEFAULT_OVERPASS_URL).strip() or DEFAULT_OVERPASS_URL
        timeout_seconds = configured_timeout_seconds()
        query = build_overpass_query(cell_lat, cell_lon, radius_m, timeout_seconds)
        await _wait_for_public_api_slot()
        try:
            counts = await asyncio.to_thread(_http_overpass, url, query, timeout_seconds)
            source_status, error_code = "available", None
        except Exception as exc:
            counts = {name: 0 for name in ("schools", "hospitals", "clinics", "bus_stops", "major_roads")}
            source_status, error_code = "unavailable", _error_code(exc)

        fetched_at = datetime.now(timezone.utc)
        _persist_cache(db, cache_key, cell_lat, cell_lon, radius_m, source_status, counts, error_code, fetched_at)
        return {
            "status": source_status,
            "counts": counts if source_status == "available" else None,
            "error_code": error_code,
            "fetched_at": fetched_at.isoformat(),
            "cache_hit": False,
            "radius_m": radius_m,
        }
