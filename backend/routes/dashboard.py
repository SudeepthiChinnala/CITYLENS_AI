from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from ..database import get_db
from ..auth import require_roles
from .. import models, schemas
from ..services import clustering_service, area_service, priority_service, insights_service

router = APIRouter()

@router.get('/summary', response_model=schemas.DashboardSummary)
async def get_summary(db: Session = Depends(get_db), _identity=Depends(require_roles('admin'))):
    total = db.query(models.Complaint).count()
    high = db.query(models.Complaint).filter(models.Complaint.severity == 'HIGH').count()
    medium = db.query(models.Complaint).filter(models.Complaint.severity == 'MEDIUM').count()
    low = db.query(models.Complaint).filter(models.Complaint.severity == 'LOW').count()
    return schemas.DashboardSummary(
        total_complaints=total,
        high_severity=high,
        medium_severity=medium,
        low_severity=low,
    )

@router.get('/areas', response_model=List[schemas.AreaStats])
async def get_area_stats(db: Session = Depends(get_db), _identity=Depends(require_roles('admin'))):
    # Get distinct areas
    areas = db.query(models.Complaint.area).distinct().all()
    result = []
    raw = []  # Pass 1: raw per-area stats
    for (area_name,) in areas:
        if not area_name:
            continue
        qry = db.query(models.Complaint).filter(models.Complaint.area == area_name)
        total = qry.count()
        high = qry.filter(models.Complaint.severity == 'HIGH').count()
        medium = qry.filter(models.Complaint.severity == 'MEDIUM').count()
        low = qry.filter(models.Complaint.severity == 'LOW').count()
        # problem type counts
        potholes = qry.filter(models.Complaint.problem_type == 'Pothole').count()
        garbage = qry.filter(models.Complaint.problem_type == 'Garbage').count()
        streetlights = qry.filter(models.Complaint.problem_type == 'Streetlight').count()
        drainage = qry.filter(models.Complaint.problem_type == 'Drainage').count()
        damaged = qry.filter(models.Complaint.problem_type == 'Damaged Road').count()
        # hotspot count (unique cluster ids in area)
        hotspots = (
            db.query(models.Complaint.cluster_id)
            .filter(models.Complaint.area == area_name, models.Complaint.cluster_id != None)
            .distinct()
            .count()
        )
        # recent complaints (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent = qry.filter(models.Complaint.timestamp >= seven_days_ago).count()
        raw.append(dict(
            area=area_name, total=total, high_severity=high, medium_severity=medium,
            low_severity=low, potholes=potholes, garbage=garbage, streetlights=streetlights,
            drainage=drainage, damaged_roads=damaged, hotspots=hotspots, recent=recent,
        ))
    if not raw:
        return result
    # Pass 2: score each area relative to the current dataset maxima (dynamic, not hardcoded)
    max_total = max(r['total'] for r in raw)
    max_high = max(r['high_severity'] for r in raw)
    max_hot = max(r['hotspots'] for r in raw)
    max_recent = max(r['recent'] for r in raw)
    for r in raw:
        recent = r.pop('recent')
        score = priority_service.compute_area_score(
            total=r['total'],
            high_severity=r['high_severity'],
            hotspots=r['hotspots'],
            recent=recent,
            max_total=max_total,
            max_high=max_high,
            max_hotspots=max_hot,
            max_recent=max_recent,
        )
        # Assign status based on score thresholds
        if score >= 80:
            status_label = 'CRITICAL'
        elif score >= 60:
            status_label = 'HIGH'
        elif score >= 40:
            status_label = 'MEDIUM'
        else:
            status_label = 'LOW'
        result.append(schemas.AreaStats(**r, score=round(score, 2), status=status_label))
    # Sort descending by score
    result.sort(key=lambda x: x.score, reverse=True)
    return result

@router.get('/clusters')
async def get_clusters(db: Session = Depends(get_db), _identity=Depends(require_roles('citizen', 'admin'))):
    return clustering_service.get_clusters_geojson(db)

@router.post('/clusters/update')
async def update_clusters_endpoint(db: Session = Depends(get_db), _identity=Depends(require_roles('admin'))):
    if not clustering_service.update_clusters(db):
        raise HTTPException(status_code=503, detail='DBSCAN recomputation is unavailable in this environment; existing cluster assignments were preserved.')
    return {'detail': 'Clusters updated'}

@router.get('/insights')
async def get_insights(db: Session = Depends(get_db), _identity=Depends(require_roles('admin'))):
    return insights_service.generate_insights(db)
