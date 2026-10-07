from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import require_roles
from ..database import get_db
from ..services.impact_priority_service import calculate_impact_priority

router = APIRouter()


@router.get('/{complaint_id}/impact-priority', response_model=schemas.ImpactPriorityOut)
async def get_complaint_impact_priority(
    complaint_id: int,
    db: Session = Depends(get_db),
    _identity=Depends(require_roles('admin')),
):
    complaint = db.query(models.Complaint).filter(models.Complaint.id == complaint_id).first()
    if complaint is None:
        raise HTTPException(status_code=404, detail='Complaint not found.')
    return await calculate_impact_priority(db, complaint)
