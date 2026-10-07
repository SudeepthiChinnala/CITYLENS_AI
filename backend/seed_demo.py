"""Reseed CityLens AI with realistic DEMO / SAMPLE complaint data for Hyderabad.

Run from project root:  python -m backend.seed_demo
- Deletes existing complaints (demo data only), inserts ~70 sample complaints.
- Deliberately creates tight groups (<~50 m) so DBSCAN (eps=0.001, min_samples=3) finds hotspots.
- Recomputes DBSCAN clusters and individual AI Priority Scores using existing services.
Does NOT change schema or API.
"""
import random
from datetime import datetime, timedelta

from .database import SessionLocal, Base, engine
from . import models
from .services import clustering_service, priority_service

random.seed(42)

DEMO_IMAGE = "dummy.png"  # placeholder image reused for all demo rows (served at /uploads/dummy.png)

AREAS = {
    "Kukatpally":   (17.4849, 78.4138),
    "Madhapur":     (17.4483, 78.3915),
    "Ameerpet":     (17.4375, 78.4482),
    "Gachibowli":   (17.4401, 78.3489),
    "LB Nagar":     (17.3457, 78.5522),
    "Secunderabad": (17.4399, 78.4983),
    "Miyapur":      (17.4968, 78.3614),
    "Hitech City":  (17.4435, 78.3772),
}

DESCRIPTIONS = {
    "Pothole": [
        "Large pothole near the bus stop. Vehicles are struggling to pass.",
        "Deep pothole in the middle of the road, two-wheelers swerving dangerously.",
        "Pothole filled with rainwater, not visible at night. Accident risk.",
        "Small pothole near the signal, getting bigger every week.",
    ],
    "Garbage": [
        "Garbage not collected for 5 days, strong smell and stray dogs.",
        "Overflowing garbage bin next to the market, waste spilling on road.",
        "Construction debris and plastic dumped on the footpath.",
        "Garbage pile near school gate, children walking past it daily.",
    ],
    "Streetlight": [
        "Streetlight not working for two weeks, lane is completely dark.",
        "Flickering streetlight near the park, unsafe for women at night.",
        "Three consecutive streetlights off on the main road.",
        "Streetlight pole damaged and leaning after the storm.",
    ],
    "Damaged Road": [
        "Road surface broken after pipeline work, never repaired.",
        "Cracked and uneven road causing traffic slowdown during peak hours.",
        "Road edge collapsed near the drain, dangerous for bikes.",
        "Speed breaker broken, loose stones scattered on the road.",
    ],
    "Drainage": [
        "Drain overflowing onto the road, sewage water stagnant.",
        "Manhole cover missing near the junction, very dangerous.",
        "Blocked drain causing waterlogging after every rain.",
        "Open drain with foul smell, mosquito breeding.",
    ],
    "Other": [
        "Fallen tree branch partially blocking the lane.",
        "Illegal hoarding blocking pedestrian path.",
    ],
}

# Hotspot groups: (area, problem_type, n_points, center offset (dlat, dlon))
HOTSPOTS = [
    ("Kukatpally", "Pothole", 6, (0.0010, -0.0008)),
    ("Kukatpally", "Garbage", 4, (-0.0060, 0.0050)),
    ("Ameerpet", "Drainage", 5, (0.0005, 0.0010)),
    ("LB Nagar", "Damaged Road", 5, (-0.0020, 0.0015)),
    ("Madhapur", "Garbage", 4, (0.0015, 0.0005)),
    ("Gachibowli", "Streetlight", 4, (-0.0010, 0.0020)),
    ("Secunderabad", "Drainage", 3, (0.0008, -0.0012)),
]

# Scattered (non-hotspot) complaints per area
SCATTER = {
    "Kukatpally": 5, "Madhapur": 5, "Ameerpet": 4, "Gachibowli": 4,
    "LB Nagar": 4, "Secunderabad": 5, "Miyapur": 6, "Hitech City": 6,
}
SCATTER_TYPES = ["Pothole", "Garbage", "Streetlight", "Damaged Road", "Drainage"]

STATUSES = ["Reported"] * 40 + ["Assigned"] * 25 + ["In Progress"] * 20 + ["Resolved"] * 15


def build_rows():
    rows = []
    for area, ptype, n, (dlat, dlon) in HOTSPOTS:
        clat, clon = AREAS[area][0] + dlat, AREAS[area][1] + dlon
        for _ in range(n):
            rows.append((area, ptype, clat + random.uniform(-0.0003, 0.0003),
                         clon + random.uniform(-0.0003, 0.0003)))
    for area, n in SCATTER.items():
        for i in range(n):
            ptype = "Other" if (area in ("Miyapur", "Hitech City") and i == 0) else random.choice(SCATTER_TYPES)
            rows.append((area, ptype, AREAS[area][0] + random.uniform(-0.012, 0.012),
                         AREAS[area][1] + random.uniform(-0.012, 0.012)))
    random.shuffle(rows)

    # Severity distribution: ~25% HIGH, ~40% MEDIUM, ~35% LOW
    n = len(rows)
    n_high, n_med = round(n * 0.25), round(n * 0.40)
    sev = ["HIGH"] * n_high + ["MEDIUM"] * n_med + ["LOW"] * (n - n_high - n_med)
    random.shuffle(sev)
    return [(a, p, la, lo, s) for (a, p, la, lo), s in zip(rows, sev)]


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        deleted = db.query(models.Complaint).delete()
        db.commit()
        print(f"Deleted {deleted} old complaints")

        now = datetime.utcnow()
        for area, ptype, lat, lon, sev in build_rows():
            ts = now - timedelta(days=random.uniform(0, 28), hours=random.uniform(0, 23))
            status = random.choice(STATUSES)
            if (now - ts).days < 2 and status == "Resolved":
                status = "Reported"
            conf = round(random.uniform(0.35, 0.55), 2) if ptype == "Other" else round(random.uniform(0.62, 0.96), 2)
            db.add(models.Complaint(
                image_path=DEMO_IMAGE,
                description="[DEMO] " + random.choice(DESCRIPTIONS[ptype]),
                problem_type=ptype,
                confidence=conf,
                severity=sev,
                latitude=round(lat, 6),
                longitude=round(lon, 6),
                area=area,
                timestamp=ts,
                status=status,
            ))
        db.commit()

        clustering_service.update_clusters(db)
        for c in db.query(models.Complaint).all():
            c.priority_score = priority_service.compute_individual_score(db, c)
        db.commit()
        print(f"Inserted {db.query(models.Complaint).count()} demo complaints; clusters + priority scores computed")
    finally:
        db.close()


if __name__ == "__main__":
    main()
