import math
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from . import severity_service
from .. import models

# Weight constants (can be tweaked)
SEVERITY_WEIGHT = 0.4
NEARBY_WEIGHT = 0.25
RECENCY_WEIGHT = 0.20
HOTSPOT_WEIGHT = 0.15

# Helper to convert severity to numeric score
SEVERITY_SCORE_MAP = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}

def _nearby_reports_count(db: Session, complaint: models.Complaint, radius: float = 0.001) -> int:
    """Count other complaints within `radius` degrees (~100m)."""
    lat, lon = complaint.latitude, complaint.longitude
    return (
        db.query(models.Complaint)
        .filter(models.Complaint.id != complaint.id)
        .filter(models.Complaint.latitude.between(lat - radius, lat + radius))
        .filter(models.Complaint.longitude.between(lon - radius, lon + radius))
        .count()
    )

def compute_individual_score(db: Session, complaint: models.Complaint) -> float:
    """Calculate priority score for a single complaint (0‑100)."""
    # Severity component (normalized 0‑1)
    sev_score = SEVERITY_SCORE_MAP.get(complaint.severity, 1) / 3.0
    # Nearby reports component (log scale to avoid huge numbers)
    nearby = _nearby_reports_count(db, complaint)
    nearby_norm = math.log1p(nearby) / math.log1p(20)  # assume 20 nearby is max for scaling
    # Recency component – newer complaints get higher score
    age_seconds = (datetime.utcnow() - complaint.timestamp).total_seconds()
    # Complaints older than 30 days get 0, newer get up to 1
    recency_norm = max(0, 1 - age_seconds / (30 * 24 * 3600))
    # Hotspot membership component
    hotspot_norm = 1.0 if complaint.cluster_id is not None else 0.0
    # Weighted sum
    raw_score = (
        sev_score * SEVERITY_WEIGHT
        + nearby_norm * NEARBY_WEIGHT
        + recency_norm * RECENCY_WEIGHT
        + hotspot_norm * HOTSPOT_WEIGHT
    )
    return round(raw_score * 100, 2)

def compute_area_score(
    total: int,
    high_severity: int,
    hotspots: int,
    recent: int,
    max_total: int = 200,
    max_high: int = 50,
    max_hotspots: int = 20,
    max_recent: int = 30,
) -> float:
    """Relative area problem score (0-100).

    Each factor is normalized against the maximum observed across all areas in the
    current dataset (callers pass the max_* values), so the most affected area scores
    near 100 and others spread proportionally. Defaults keep the legacy fixed caps.
    Weights: complaints 35%, high-severity 35%, hotspots 20%, recent (7d) 10%.
    """
    def norm(v, m):
        return min(v / m, 1.0) if m and m > 0 else 0.0

    score = (
        norm(total, max_total) * 0.35
        + norm(high_severity, max_high) * 0.35
        + norm(hotspots, max_hotspots) * 0.20
        + norm(recent, max_recent) * 0.10
    )
    return round(score * 100, 2)
