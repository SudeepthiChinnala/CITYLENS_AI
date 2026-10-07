import re
from typing import List, Tuple
from sqlalchemy.orm import Session
from .. import models

# Parameters for DBSCAN – these can be tuned later
EPS = 0.001  # approx 100 meters (in decimal degrees)
MIN_SAMPLES = 3

def update_clusters(db: Session) -> bool:
    """Recompute DBSCAN clusters for all complaints and store cluster_id.
    Complaints without enough neighbours get cluster_id = None.
    """
    try:
        import numpy as np
        from sklearn.cluster import DBSCAN
    except (ImportError, OSError) as exc:
        print(f'DBSCAN update unavailable; existing cluster assignments were preserved: {exc}')
        return False
    complaints = db.query(models.Complaint).all()
    if not complaints:
        return True
    coords = np.array([[c.latitude, c.longitude] for c in complaints])
    clustering = DBSCAN(eps=EPS, min_samples=MIN_SAMPLES).fit(coords)
    labels = clustering.labels_  # -1 means noise
    for complaint, label in zip(complaints, labels):
        complaint.cluster_id = None if label == -1 else int(label)
    db.commit()
    return True

def get_clusters_geojson(db: Session) -> dict:
    """Return GeoJSON FeatureCollection of clusters with centroid and size.
    Each feature includes properties: cluster_id, count, problem_type (most common), avg_severity.
    """
    from collections import defaultdict, Counter
    complaints = db.query(models.Complaint).filter(models.Complaint.cluster_id != None).all()
    if not complaints:
        return {"type": "FeatureCollection", "features": []}
    clusters = defaultdict(list)
    for c in complaints:
        clusters[c.cluster_id].append(c)
    features = []
    for cid, members in clusters.items():
        lats = [m.latitude for m in members]
        lons = [m.longitude for m in members]
        centroid = [sum(lats) / len(lats), sum(lons) / len(lons)]
        problem_counts = Counter([m.problem_type for m in members])
        main_problem = problem_counts.most_common(1)[0][0]
        severity_scores = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3}
        avg_sev = sum(severity_scores.get(m.severity, 1) for m in members) / len(members)
        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [centroid[1], centroid[0]]},
            "properties": {
                "cluster_id": cid,
                "count": len(members),
                "problem_type": main_problem,
                "avg_severity": round(avg_sev, 2),
            },
        }
        features.append(feature)
    return {"type": "FeatureCollection", "features": features}
