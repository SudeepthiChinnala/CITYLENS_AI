"""Explainable estimated impact priority, kept separate from the legacy score."""
from __future__ import annotations

import math
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from .osm_exposure_service import get_nearby_exposure

SEVERITY_SCORE = {"LOW": 40, "MEDIUM": 70, "HIGH": 100}
MAX_RECURRENCE_COUNT = 5
DEFAULT_RECURRENCE_RADIUS_M = 500
DEFAULT_RECURRENCE_WINDOW_DAYS = 365


def _bounded_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        return min(max(int(os.getenv(name, str(default))), minimum), maximum)
    except (TypeError, ValueError):
        return default


def recurrence_radius_m() -> int:
    return _bounded_int_env("CITYLENS_RECURRENCE_RADIUS_METERS", DEFAULT_RECURRENCE_RADIUS_M, 100, 2000)


def recurrence_window_days() -> int:
    return _bounded_int_env("CITYLENS_RECURRENCE_WINDOW_DAYS", DEFAULT_RECURRENCE_WINDOW_DAYS, 1, 3650)


def _valid_coordinates(latitude, longitude) -> bool:
    return (
        isinstance(latitude, (int, float)) and isinstance(longitude, (int, float))
        and math.isfinite(latitude) and math.isfinite(longitude)
        and -90 <= latitude <= 90 and -180 <= longitude <= 180
    )


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_m = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return earth_radius_m * 2 * math.asin(math.sqrt(min(1.0, a)))


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def count_related_incidents(db: Session, complaint: models.Complaint, radius_m: int | None = None, window_days: int | None = None) -> int:
    """Count other stored same-type incidents within a past window and radius.

    Missing/invalid coordinates, problem type, or timestamp means no reliable
    recurrence evidence; no synthetic history is added.
    """
    if not _valid_coordinates(complaint.latitude, complaint.longitude) or not complaint.problem_type or not complaint.timestamp:
        return 0
    radius = radius_m if radius_m is not None else recurrence_radius_m()
    days = window_days if window_days is not None else recurrence_window_days()
    current_time = _as_utc(complaint.timestamp)
    start_time = current_time - timedelta(days=days)
    lat_delta = radius / 110_574.0
    cos_lat = max(abs(math.cos(math.radians(complaint.latitude))), 0.01)
    lon_delta = radius / (111_320.0 * cos_lat)
    candidates = db.query(models.Complaint).filter(
        models.Complaint.id != complaint.id,
        func.lower(models.Complaint.problem_type) == complaint.problem_type.strip().lower(),
        models.Complaint.latitude.between(complaint.latitude - lat_delta, complaint.latitude + lat_delta),
        models.Complaint.longitude.between(complaint.longitude - lon_delta, complaint.longitude + lon_delta),
        models.Complaint.timestamp >= start_time.replace(tzinfo=None),
        models.Complaint.timestamp <= current_time.replace(tzinfo=None),
    ).all()
    return sum(
        1 for row in candidates
        if _valid_coordinates(row.latitude, row.longitude)
        and row.timestamp is not None
        and _haversine_m(complaint.latitude, complaint.longitude, row.latitude, row.longitude) <= radius
    )


def _exposure_score(counts: dict) -> int:
    # Raw feature weights are capped per category, then normalized to 0–100:
    # school 10 x max 2 (20), hospital 20 x max 2 (40), clinic 10 x max 2 (20),
    # public transport stop 2 x max 4 (8), any major-road feature (12).
    raw = (
        min(int(counts.get("schools", 0)), 2) * 10
        + min(int(counts.get("hospitals", 0)), 2) * 20
        + min(int(counts.get("clinics", 0)), 2) * 10
        + min(int(counts.get("bus_stops", 0)), 4) * 2
        + (12 if int(counts.get("major_roads", 0)) > 0 else 0)
    )
    return min(100, max(0, int(math.floor(raw + 0.5))))


def _explanation(severity: str, severity_score: int, counts: dict, exposure_score: int, recurrence_count: int, recurrence_score: int, osm_radius_m: int, recurrence_radius: int, window_days: int) -> str:
    road = "present" if counts.get("major_roads", 0) else "not found"
    return (
        f"Estimated exposure based on mapped public infrastructure within {osm_radius_m} m, not a people count. "
        f"Severity {severity} contributes {severity_score}/100; OSM returned {counts.get('schools', 0)} schools, "
        f"{counts.get('hospitals', 0)} hospitals, {counts.get('clinics', 0)} clinics, "
        f"{counts.get('bus_stops', 0)} public-transport stops, and major-road features are {road} "
        f"(exposure {exposure_score}/100). "
        f"Recurrence counts {recurrence_count} other same-type stored complaints within {recurrence_radius} m over the "
        f"past {window_days} days (recurrence {recurrence_score}/100). Composite weights are 50% severity, "
        "35% exposure and 15% recurrence. OSM coverage may be incomplete."
    )


async def calculate_impact_priority(db: Session, complaint: models.Complaint) -> dict:
    complaint_id = complaint.id
    legacy_priority_score = complaint.priority_score
    latitude, longitude = complaint.latitude, complaint.longitude
    severity = str(complaint.severity or "LOW").upper()
    severity_score = SEVERITY_SCORE.get(severity, SEVERITY_SCORE["LOW"])
    radius_m = recurrence_radius_m()
    window_days = recurrence_window_days()
    related_count = count_related_incidents(db, complaint, radius_m, window_days)
    recurrence_score = min(related_count, MAX_RECURRENCE_COUNT) * 20
    osm = await get_nearby_exposure(db, latitude, longitude)
    component_methodology = (
        f"Severity: LOW=40, MEDIUM=70, HIGH=100. Exposure: up to 2 schools ×10, 2 hospitals ×20, "
        f"2 clinics ×10, 4 public-transport stops ×2, plus 12 if any major-road feature is mapped; cap 100. "
        f"Recurrence: same problem type within {radius_m} m in the past {window_days} days; 20 points per "
        "related complaint, capped at 5 complaints (100)."
    )

    result = {
        "complaint_id": complaint_id,
        "legacy_priority_score": legacy_priority_score,
        "impact_priority_score": None,
        "severity": severity,
        "severity_score": severity_score,
        "exposure_score": None,
        "recurrence_count": related_count,
        "recurrence_score": recurrence_score,
        "nearby_schools": None,
        "nearby_hospitals": None,
        "nearby_clinics": None,
        "nearby_bus_stops": None,
        "nearby_major_roads": None,
        "major_road_proximity": None,
        "osm_status": osm["status"],
        "osm_error_code": osm.get("error_code"),
        "osm_cache_hit": osm.get("cache_hit", False),
        "osm_fetched_at": osm.get("fetched_at"),
        "osm_radius_m": osm.get("radius_m"),
        "recurrence_radius_m": radius_m,
        "recurrence_window_days": window_days,
        "formula": "round(0.50 × severity_score + 0.35 × exposure_score + 0.15 × recurrence_score)",
        "component_methodology": component_methodology,
        "explanation": "",
        "fallback_reason": None,
        "attribution": "© OpenStreetMap contributors",
    }

    if osm["status"] != "available" or not osm.get("counts"):
        reason = (
            "Valid coordinates are required before nearby infrastructure can be estimated."
            if osm["status"] == "invalid_coordinates"
            else "OpenStreetMap/Overpass data is temporarily unavailable; the existing CityLens priority remains in use."
        )
        result["fallback_reason"] = reason
        result["explanation"] = reason
        return result

    counts = osm["counts"]
    exposure_score = _exposure_score(counts)
    weighted_score = 0.50 * severity_score + 0.35 * exposure_score + 0.15 * recurrence_score
    score = int(math.floor(weighted_score + 0.5))
    score = min(100, max(0, score))
    result.update({
        "impact_priority_score": score,
        "exposure_score": exposure_score,
        "nearby_schools": counts.get("schools", 0),
        "nearby_hospitals": counts.get("hospitals", 0),
        "nearby_clinics": counts.get("clinics", 0),
        "nearby_bus_stops": counts.get("bus_stops", 0),
        "nearby_major_roads": counts.get("major_roads", 0),
        "major_road_proximity": counts.get("major_roads", 0) > 0,
        "explanation": _explanation(severity, severity_score, counts, exposure_score, related_count, recurrence_score, osm.get("radius_m", 500), radius_m, window_days),
    })
    return result
