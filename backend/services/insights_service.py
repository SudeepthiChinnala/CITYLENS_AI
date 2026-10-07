from sqlalchemy.orm import Session
from sqlalchemy import func
from .. import models
from datetime import datetime, timedelta

def generate_insights(db: Session) -> dict:
    """Generate simple textual insights for the dashboard.
    Returns a dict with a list of insight strings.
    """
    insights = []
    # Example: increase in potholes compared to previous week
    now = datetime.utcnow()
    last_week = now - timedelta(days=7)
    prev_week = now - timedelta(days=14)
    # Count current week complaints per type
    cur_counts = (
        db.query(models.Complaint.problem_type, func.count(models.Complaint.id))
        .filter(models.Complaint.timestamp >= last_week)
        .group_by(models.Complaint.problem_type)
        .all()
    )
    # Count previous week
    prev_counts = (
        db.query(models.Complaint.problem_type, func.count(models.Complaint.id))
        .filter(models.Complaint.timestamp.between(prev_week, last_week))
        .group_by(models.Complaint.problem_type)
        .all()
    )
    cur_dict = dict(cur_counts)
    prev_dict = dict(prev_counts)
    for prob_type, cur_val in cur_dict.items():
        prev_val = prev_dict.get(prob_type, 0)
        if prev_val == 0:
            change = "new"
        else:
            pct = ((cur_val - prev_val) / prev_val) * 100
            change = f"{pct:.0f}% increase" if pct > 0 else f"{abs(pct):.0f}% decrease"
        insights.append(f"{prob_type}: {cur_val} reports this week ({change} over last week)")
    # Hotspot insight: area with most hotspots (distinct DBSCAN clusters, not member complaints)
    distinct_clusters = func.count(func.distinct(models.Complaint.cluster_id))
    hot_areas = (
        db.query(models.Complaint.area, distinct_clusters)
        .filter(models.Complaint.cluster_id != None)
        .group_by(models.Complaint.area)
        .order_by(distinct_clusters.desc())
        .limit(1)
        .first()
    )
    if hot_areas:
        label = "hotspot" if hot_areas[1] == 1 else "hotspots"
        insights.append(f"Area with most hotspots: {hot_areas[0]} ({hot_areas[1]} {label})")
    return {"insights": insights}
