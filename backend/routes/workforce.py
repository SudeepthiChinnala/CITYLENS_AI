from datetime import datetime, timezone
import os
import re
import shutil
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import PortalIdentity, hash_password, require_roles
from ..database import get_db
from .complaints import (
    EVIDENCE_UPLOAD_DIR,
    MAX_EVIDENCE_IMAGE_BYTES,
    _inspect_evidence_image,
    _safe_evidence_path,
)

router = APIRouter(prefix="/workforce", tags=["workforce"])

WORK_STATUSES = ("Assigned", "Accepted", "Work Started", "In Progress", "Work Completed")
NEXT_STATUSES = {
    "Assigned": {"Accepted"},
    "Accepted": {"Work Started"},
    "Work Started": {"In Progress"},
    "In Progress": {"In Progress", "Work Completed"},
}
WORKER_OVERLOAD_THRESHOLD = 5


def _now():
    return datetime.now(timezone.utc)


def _as_utc(value):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _is_overdue(assignment):
    deadline = _as_utc(assignment.deadline)
    return bool(deadline and assignment.status != "Work Completed" and deadline < _now())


def _worker_stats(db: Session, worker_id: str):
    assignments = db.query(models.ComplaintAssignment).filter_by(worker_id=worker_id).all()
    current = [row for row in assignments if row.active]
    active_count = sum(row.status != "Work Completed" for row in current)
    completed_count = sum(row.status == "Work Completed" for row in assignments)
    today = _now().date()
    return {
        "total_assigned": len(current),
        "active": active_count,
        "pending": sum(row.status == "Assigned" for row in current),
        "accepted": sum(row.status == "Accepted" for row in current),
        "work_started": sum(row.status == "Work Started" for row in current),
        "in_progress": sum(row.status == "In Progress" for row in current),
        "completed": completed_count,
        "overdue": sum(_is_overdue(row) for row in current),
        "assigned_today": sum(bool(row.assigned_at and _as_utc(row.assigned_at).date() == today) for row in current),
        "completion_rate": round(completed_count / len(assignments) * 100, 1) if assignments else 0.0,
        "overloaded": active_count >= WORKER_OVERLOAD_THRESHOLD,
    }


def _worker_out(db: Session, worker: models.WorkerAccount):
    return {
        "worker_id": worker.worker_id,
        "full_name": worker.full_name,
        "phone": worker.phone,
        "department": worker.department,
        "account_status": worker.account_status,
        "created_at": worker.created_at,
        **_worker_stats(db, worker.worker_id),
    }


def _assignment_summary(db: Session, assignment: models.ComplaintAssignment, *, admin: bool):
    complaint = db.query(models.Complaint).filter_by(id=assignment.complaint_id).first()
    worker = db.query(models.WorkerAccount).filter_by(worker_id=assignment.worker_id).first()
    latest = db.query(models.WorkerProgressUpdate).filter_by(assignment_id=assignment.id).order_by(
        models.WorkerProgressUpdate.id.desc()
    ).first()
    result = {
        "assignment_id": assignment.id,
        "complaint_id": assignment.complaint_id,
        "worker_name": worker.full_name if worker else "Unavailable",
        "department": worker.department if worker else "—",
        "assigned_at": assignment.assigned_at,
        "deadline": assignment.deadline,
        "status": assignment.status,
        "progress_percentage": assignment.progress_percentage,
        "active": assignment.active,
        "overdue": _is_overdue(assignment),
        "last_updated": latest.created_at if latest else assignment.assigned_at,
        "latest_comment": latest.comment if latest else assignment.assignment_note,
    }
    if admin:
        result.update({
            "worker_id": assignment.worker_id,
            "worker_phone": worker.phone if worker else None,
            "assigned_by": assignment.assigned_by,
            "assignment_note": assignment.assignment_note,
        })
    if complaint:
        result.update({
            "problem_type": complaint.problem_type,
            "image_url": f"/api/complaints/{complaint.id}/image",
            "description": complaint.description,
            "area": complaint.area,
            "severity": complaint.severity,
            "priority_score": complaint.priority_score,
            "latitude": complaint.latitude,
            "longitude": complaint.longitude,
            "complaint_status": complaint.status,
            "complaint_timestamp": complaint.timestamp,
        })
    return result


def _progress_data(db: Session, complaint: models.Complaint, identity: PortalIdentity):
    assignments = db.query(models.ComplaintAssignment).filter_by(complaint_id=complaint.id).order_by(
        models.ComplaintAssignment.assigned_at,
        models.ComplaintAssignment.id,
    ).all()
    if identity.role == "worker":
        assignments = [row for row in assignments if row.worker_id == identity.account_id and row.active]
    assignment_ids = [row.id for row in assignments]
    worker_updates = []
    if assignment_ids:
        worker_updates = db.query(models.WorkerProgressUpdate).filter(
            models.WorkerProgressUpdate.assignment_id.in_(assignment_ids)
        ).order_by(models.WorkerProgressUpdate.created_at, models.WorkerProgressUpdate.id).all()
    work_updates = db.query(models.ComplaintWorkUpdate).filter_by(complaint_id=complaint.id).order_by(
        models.ComplaintWorkUpdate.uploaded_at,
        models.ComplaintWorkUpdate.id,
    ).all()
    confirmations = db.query(models.CitizenResolutionConfirmation).filter_by(
        complaint_id=complaint.id,
    ).order_by(models.CitizenResolutionConfirmation.created_at, models.CitizenResolutionConfirmation.id).all()

    public_assignments = []
    timeline = [{
        "event_id": f"complaint-{complaint.id}",
        "event_type": "complaint_submitted",
        "status": "Reported",
        "message": "Complaint submitted.",
        "created_at": complaint.timestamp,
    }]
    for assignment in assignments:
        worker = db.query(models.WorkerAccount).filter_by(worker_id=assignment.worker_id).first()
        public_assignments.append({
            "assignment_id": assignment.id,
            "worker_name": worker.full_name if worker else "Unavailable",
            "department": worker.department if worker else "—",
            "assigned_at": assignment.assigned_at,
            "deadline": assignment.deadline,
            "status": assignment.status,
            "progress_percentage": assignment.progress_percentage,
            "active": assignment.active,
            **({"worker_id": assignment.worker_id, "worker_phone": worker.phone if worker else None,
                "assignment_note": assignment.assignment_note, "assigned_by": assignment.assigned_by}
               if identity.role == "admin" else {}),
        })
        timeline.append({
            "event_id": f"assignment-{assignment.id}",
            "event_type": "assignment",
            "status": "Assigned",
            "worker_name": worker.full_name if worker else "Unavailable",
            "department": worker.department if worker else "—",
            "message": assignment.assignment_note if identity.role == "admin" else None,
            "created_at": assignment.assigned_at,
        })

    updates_out = []
    for update in worker_updates:
        safe_photo = _safe_evidence_path(update.evidence_photo_path)
        photo_url = f"/api/workforce/progress-updates/{update.id}/photo" if safe_photo else None
        label = "Workforce team" if identity.role == "citizen" else update.updated_by
        item = {
            "id": update.id,
            "assignment_id": update.assignment_id,
            "previous_status": update.previous_status,
            "status": update.new_status,
            "progress_percentage": update.progress_percentage,
            "comment": update.comment,
            "photo_url": photo_url,
            "updated_by": label,
            "created_at": update.created_at,
        }
        if identity.role == "admin":
            item.update({
                "worker_id": update.worker_id,
                "file_hash": update.file_hash,
                "authenticity_status": update.authenticity_status,
                "metadata_summary": update.metadata_summary,
            })
        updates_out.append(item)
        event = {
            "event_id": f"worker-update-{update.id}",
            "event_type": "worker_update",
            "status": update.new_status,
            "progress_percentage": update.progress_percentage,
            "message": update.comment,
            "photo_url": photo_url,
            "updated_by": label,
            "created_at": update.created_at,
        }
        if identity.role == "admin":
            event.update({
                "file_hash": update.file_hash,
                "authenticity_status": update.authenticity_status,
                "metadata_summary": update.metadata_summary,
            })
        timeline.append(event)

    for update in work_updates:
        safe_photo = _safe_evidence_path(update.photo_path)
        timeline.append({
            "event_id": f"authority-update-{update.id}",
            "event_type": "authority_update",
            "status": update.status,
            "message": update.message,
            "photo_url": f"/api/complaints/work-updates/{update.id}/photo" if safe_photo else None,
            "updated_by": "City authority",
            "created_at": update.uploaded_at,
        })
    if identity.role != "worker":
        for event in confirmations:
            timeline.append({
                "event_id": f"citizen-confirmation-{event.id}",
                "event_type": "citizen_confirmation",
                "status": event.response,
                "message": "Citizen confirmed the issue was fixed." if event.response == "confirmed" else "Citizen reported that the issue remains unresolved.",
                "created_at": event.created_at,
            })

    def timeline_sort_key(item):
        return _as_utc(item["created_at"]).timestamp() if item.get("created_at") else 0

    timeline.sort(key=timeline_sort_key)
    current = next((row for row in reversed(assignments) if row.active), assignments[-1] if assignments else None)
    current_summary = _assignment_summary(db, current, admin=identity.role == "admin") if current else None
    return {
        "complaint_id": complaint.id,
        "complaint_status": complaint.status,
        "current_assignment": current_summary,
        "assignment_history": public_assignments,
        "work_updates": updates_out,
        "timeline": timeline,
    }


def _authorized_complaint(db: Session, complaint_id: int, identity: PortalIdentity):
    complaint = db.query(models.Complaint).filter_by(id=complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found.")
    if identity.role == "citizen" and complaint.citizen_id != identity.account_id:
        raise HTTPException(status_code=404, detail="Complaint not found.")
    if identity.role == "worker":
        worker = db.query(models.WorkerAccount).filter_by(
            worker_id=identity.account_id,
            account_status="active",
        ).first()
        if not worker:
            raise HTTPException(status_code=403, detail="This worker account is inactive.")
        assigned = db.query(models.ComplaintAssignment.id).filter_by(
            complaint_id=complaint.id,
            worker_id=identity.account_id,
            active=True,
        ).first()
        if not assigned:
            raise HTTPException(status_code=404, detail="Complaint not found.")
    return complaint


def _worker_assignments_payload(db: Session, worker: models.WorkerAccount, *, include_history=True):
    query = db.query(models.ComplaintAssignment).filter_by(worker_id=worker.worker_id)
    if not include_history:
        query = query.filter_by(active=True)
    assignments = query.order_by(models.ComplaintAssignment.assigned_at.desc()).limit(200).all()
    return [_assignment_summary(db, item, admin=False) for item in assignments]


@router.post("/admin/workers", status_code=status.HTTP_201_CREATED)
async def create_worker(
    payload: schemas.WorkerCreateIn,
    db: Session = Depends(get_db),
    admin: PortalIdentity = Depends(require_roles("admin")),
):
    del admin  # Authorization is enforced by the dependency; no admin secret is stored here.
    worker_id = payload.worker_id.strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{2,31}", worker_id):
        raise HTTPException(status_code=400, detail="Worker ID must use 3–32 letters, numbers, dots, underscores, or hyphens.")
    full_name = payload.full_name.strip()
    department = payload.department.strip()
    if len(full_name) < 2 or len(department) < 2:
        raise HTTPException(status_code=400, detail="Enter a full name and department with at least two non-space characters.")
    if db.query(models.WorkerAccount).filter_by(worker_id=worker_id).first():
        raise HTTPException(status_code=409, detail="A worker with that ID already exists.")
    worker = models.WorkerAccount(
        worker_id=worker_id,
        full_name=full_name,
        phone=payload.phone.strip() if payload.phone and payload.phone.strip() else None,
        department=department,
        password_hash=hash_password(payload.password),
        account_status="active",
        created_at=_now(),
    )
    db.add(worker)
    try:
        db.commit()
        db.refresh(worker)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A worker with that ID already exists.") from exc
    return _worker_out(db, worker)


@router.get("/admin/summary")
async def get_workforce_summary(
    db: Session = Depends(get_db),
    _admin: PortalIdentity = Depends(require_roles("admin")),
):
    workers = db.query(models.WorkerAccount).all()
    assignments = db.query(models.ComplaintAssignment).filter_by(active=True).all()
    all_assignments_count = db.query(models.ComplaintAssignment).count()
    completed_count = db.query(models.ComplaintAssignment).filter_by(status="Work Completed").count()
    worker_stats = [_worker_stats(db, worker.worker_id) for worker in workers if worker.account_status == "active"]
    active_assignment_ids = db.query(models.ComplaintAssignment.complaint_id).filter_by(active=True)
    unassigned_complaints = db.query(models.Complaint).filter(
        models.Complaint.status != "Resolved",
        ~models.Complaint.id.in_(active_assignment_ids),
    ).count()
    return {
        "total_workers": len(workers),
        "active_workers": sum(worker.account_status == "active" for worker in workers),
        "total_assigned": len(assignments),
        "active": sum(item.status != "Work Completed" for item in assignments),
        "pending": sum(item.status == "Assigned" for item in assignments),
        "accepted": sum(item.status == "Accepted" for item in assignments),
        "work_started": sum(item.status == "Work Started" for item in assignments),
        "in_progress": sum(item.status == "In Progress" for item in assignments),
        "completed": completed_count,
        "overdue": sum(_is_overdue(item) for item in assignments),
        "unassigned_complaints": unassigned_complaints,
        "overloaded_workers": sum(stats["overloaded"] for stats in worker_stats),
        "overload_threshold_active_cases": WORKER_OVERLOAD_THRESHOLD,
        "completion_rate": round(completed_count / all_assignments_count * 100, 1) if all_assignments_count else 0.0,
    }


@router.get("/admin/workers")
async def list_workers(
    db: Session = Depends(get_db),
    _admin: PortalIdentity = Depends(require_roles("admin")),
):
    workers = db.query(models.WorkerAccount).order_by(models.WorkerAccount.full_name, models.WorkerAccount.worker_id).all()
    return [_worker_out(db, worker) for worker in workers]


@router.get("/admin/workers/{worker_id}")
async def get_worker_profile(
    worker_id: str,
    db: Session = Depends(get_db),
    _admin: PortalIdentity = Depends(require_roles("admin")),
):
    worker = db.query(models.WorkerAccount).filter_by(worker_id=worker_id.upper()).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found.")
    return {
        **_worker_out(db, worker),
        "assignments": [
            _assignment_summary(db, item, admin=True)
            for item in db.query(models.ComplaintAssignment).filter_by(worker_id=worker.worker_id)
            .order_by(models.ComplaintAssignment.assigned_at.desc()).limit(200).all()
        ],
    }


@router.patch("/admin/workers/{worker_id}/status")
async def update_worker_status(
    worker_id: str,
    payload: schemas.WorkerAccountStatusIn,
    db: Session = Depends(get_db),
    _admin: PortalIdentity = Depends(require_roles("admin")),
):
    worker = db.query(models.WorkerAccount).filter_by(worker_id=worker_id.upper()).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found.")
    worker.account_status = payload.account_status
    db.commit()
    db.refresh(worker)
    return _worker_out(db, worker)


@router.post("/admin/complaints/{complaint_id}/assignments", status_code=status.HTTP_201_CREATED)
async def assign_complaint(
    complaint_id: int,
    payload: schemas.ComplaintAssignmentIn,
    db: Session = Depends(get_db),
    admin: PortalIdentity = Depends(require_roles("admin")),
):
    complaint = db.query(models.Complaint).filter_by(id=complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found.")
    if complaint.status == "Resolved":
        raise HTTPException(status_code=409, detail="Reopen the resolved complaint before assigning more work.")
    worker = db.query(models.WorkerAccount).filter_by(worker_id=payload.worker_id.strip().upper()).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found.")
    if worker.account_status != "active":
        raise HTTPException(status_code=409, detail="This worker account is suspended and cannot receive assignments.")
    if payload.deadline and _as_utc(payload.deadline) <= _now():
        raise HTTPException(status_code=400, detail="The assignment deadline must be in the future.")

    for previous in db.query(models.ComplaintAssignment).filter_by(complaint_id=complaint.id, active=True).all():
        previous.active = False
    assignment = models.ComplaintAssignment(
        complaint_id=complaint.id,
        worker_id=worker.worker_id,
        assigned_by=admin.account_id,
        assigned_at=_now(),
        deadline=payload.deadline,
        assignment_note=payload.note.strip() if payload.note and payload.note.strip() else None,
        active=True,
        status="Assigned",
        progress_percentage=0,
    )
    db.add(assignment)
    complaint.status = "Assigned"
    try:
        db.flush()
        db.add(models.WorkerProgressUpdate(
            complaint_id=complaint.id,
            assignment_id=assignment.id,
            worker_id=worker.worker_id,
            previous_status=None,
            new_status="Assigned",
            progress_percentage=0,
            comment=assignment.assignment_note,
            evidence_photo_path=None,
            updated_by=admin.account_id,
            created_at=_now(),
        ))
        db.commit()
        db.refresh(assignment)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not save the complaint assignment.") from exc
    return _assignment_summary(db, assignment, admin=True)


@router.post("/admin/complaints/{complaint_id}/verify-completion")
async def verify_worker_completion(
    complaint_id: int,
    payload: schemas.WorkVerificationIn,
    db: Session = Depends(get_db),
    admin: PortalIdentity = Depends(require_roles("admin")),
):
    complaint = db.query(models.Complaint).filter_by(id=complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found.")
    assignment = db.query(models.ComplaintAssignment).filter_by(complaint_id=complaint.id, active=True).order_by(
        models.ComplaintAssignment.id.desc()
    ).first()
    if not assignment or assignment.status != "Work Completed":
        raise HTTPException(status_code=409, detail="There is no worker completion awaiting verification.")
    completion = db.query(models.WorkerProgressUpdate).filter_by(
        assignment_id=assignment.id,
        new_status="Work Completed",
    ).order_by(models.WorkerProgressUpdate.id.desc()).first()
    if not completion or not _safe_evidence_path(completion.evidence_photo_path):
        raise HTTPException(status_code=409, detail="The worker completion photo is unavailable; this work cannot be verified.")

    work_update = models.ComplaintWorkUpdate(
        complaint_id=complaint.id,
        status="Resolved",
        message=(payload.note.strip() if payload.note and payload.note.strip() else completion.comment or "Worker completion verified by the CityLens authority."),
        photo_path=completion.evidence_photo_path,
        uploaded_by=admin.account_id,
        uploaded_at=_now(),
        file_hash=completion.file_hash,
        authenticity_status=completion.authenticity_status,
        metadata_summary=completion.metadata_summary,
    )
    complaint.status = "Resolved"
    assignment.active = False
    db.add(work_update)
    try:
        db.commit()
        db.refresh(work_update)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not save Admin verification.") from exc
    return {
        "complaint_id": complaint.id,
        "complaint_status": complaint.status,
        "resolution_update_id": work_update.id,
        "verified_at": work_update.uploaded_at,
        "message": work_update.message,
    }


@router.get("/my")
async def get_worker_dashboard(
    db: Session = Depends(get_db),
    worker_identity: PortalIdentity = Depends(require_roles("worker")),
):
    worker = db.query(models.WorkerAccount).filter_by(worker_id=worker_identity.account_id).first()
    if not worker or worker.account_status != "active":
        raise HTTPException(status_code=403, detail="This worker account is inactive.")
    return {
        "worker": {
            "worker_id": worker.worker_id,
            "full_name": worker.full_name,
            "department": worker.department,
        },
        "summary": _worker_stats(db, worker.worker_id),
        "assignments": _worker_assignments_payload(db, worker, include_history=False),
    }


@router.post("/assignments/{assignment_id}/updates", status_code=status.HTTP_201_CREATED)
async def create_worker_progress_update(
    assignment_id: int,
    new_status: str = Form(...),
    progress_percentage: int = Form(...),
    comment: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    worker_identity: PortalIdentity = Depends(require_roles("worker")),
):
    assignment = db.query(models.ComplaintAssignment).filter_by(id=assignment_id).first()
    if not assignment or assignment.worker_id != worker_identity.account_id or not assignment.active:
        raise HTTPException(status_code=404, detail="Active assignment not found.")
    worker = db.query(models.WorkerAccount).filter_by(worker_id=worker_identity.account_id).first()
    if not worker or worker.account_status != "active":
        raise HTTPException(status_code=403, detail="This worker account is inactive.")
    if new_status not in WORK_STATUSES or new_status not in NEXT_STATUSES.get(assignment.status, set()):
        raise HTTPException(status_code=409, detail=f"Invalid work-stage transition from {assignment.status}.")
    if not 0 <= progress_percentage <= 100:
        raise HTTPException(status_code=400, detail="Progress must be between 0 and 100 percent.")
    if progress_percentage < assignment.progress_percentage:
        raise HTTPException(status_code=409, detail="Work progress cannot move backwards.")
    if new_status == "Accepted" and progress_percentage != 0:
        raise HTTPException(status_code=400, detail="Acceptance starts at 0 percent.")
    if new_status == "Work Completed":
        if progress_percentage != 100:
            raise HTTPException(status_code=400, detail="Mark Work Completed only at 100 percent.")
        if photo is None:
            raise HTTPException(status_code=400, detail="A completion photo is required before submitting work for Admin verification.")
    elif progress_percentage >= 100:
        raise HTTPException(status_code=400, detail="100 percent progress is reserved for Work Completed.")
    comment = (comment or "").strip() or None
    if comment and len(comment) > 2000:
        raise HTTPException(status_code=400, detail="Work comments must be 2,000 characters or fewer.")

    photo_name = None
    file_hash = None
    authenticity_status = "No photo uploaded; no authenticity check performed."
    metadata_summary = None
    saved_path = None
    if photo is not None:
        content = await photo.read(MAX_EVIDENCE_IMAGE_BYTES + 1)
        if len(content) > MAX_EVIDENCE_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Evidence photos must be 10 MB or smaller.")
        if not content:
            raise HTTPException(status_code=400, detail="The selected evidence photo is empty.")
        extension, file_hash, authenticity_status, metadata_summary = _inspect_evidence_image(content)
        photo_name = f"{uuid.uuid4().hex}{extension}"
        saved_path = os.path.join(EVIDENCE_UPLOAD_DIR, photo_name)
        try:
            with open(saved_path, "xb") as image_file:
                image_file.write(content)
        except OSError as exc:
            raise HTTPException(status_code=500, detail="Could not store the work evidence photo.") from exc

    previous_status = assignment.status
    update = models.WorkerProgressUpdate(
        complaint_id=assignment.complaint_id,
        assignment_id=assignment.id,
        worker_id=worker_identity.account_id,
        previous_status=previous_status,
        new_status=new_status,
        progress_percentage=progress_percentage,
        comment=comment,
        evidence_photo_path=photo_name,
        updated_by=worker_identity.account_id,
        created_at=_now(),
        file_hash=file_hash,
        authenticity_status=authenticity_status,
        metadata_summary=metadata_summary,
    )
    complaint = db.query(models.Complaint).filter_by(id=assignment.complaint_id).first()
    assignment.status = new_status
    assignment.progress_percentage = progress_percentage
    if complaint:
        if new_status in {"Work Started", "In Progress"}:
            complaint.status = "In Progress"
        elif new_status == "Work Completed":
            complaint.status = "Under Review"
    db.add(update)
    try:
        db.commit()
        db.refresh(update)
    except Exception as exc:
        db.rollback()
        if saved_path and os.path.isfile(saved_path):
            os.remove(saved_path)
        raise HTTPException(status_code=500, detail="Could not save the work progress update.") from exc
    return {
        "id": update.id,
        "assignment_id": update.assignment_id,
        "complaint_id": update.complaint_id,
        "previous_status": update.previous_status,
        "status": update.new_status,
        "progress_percentage": update.progress_percentage,
        "comment": update.comment,
        "photo_url": f"/api/workforce/progress-updates/{update.id}/photo" if photo_name else None,
        "created_at": update.created_at,
    }


@router.get("/complaints/{complaint_id}/progress")
async def get_complaint_workforce_progress(
    complaint_id: int,
    db: Session = Depends(get_db),
    identity: PortalIdentity = Depends(require_roles("admin", "citizen", "worker")),
):
    complaint = _authorized_complaint(db, complaint_id, identity)
    return _progress_data(db, complaint, identity)


@router.get("/progress-updates/{update_id}/photo")
async def get_worker_progress_photo(
    update_id: int,
    db: Session = Depends(get_db),
    identity: PortalIdentity = Depends(require_roles("admin", "citizen", "worker")),
):
    update = db.query(models.WorkerProgressUpdate).filter_by(id=update_id).first()
    complaint = db.query(models.Complaint).filter_by(id=update.complaint_id).first() if update else None
    if not update or not complaint:
        raise HTTPException(status_code=404, detail="Evidence photo not found.")
    if identity.role == "citizen" and complaint.citizen_id != identity.account_id:
        raise HTTPException(status_code=404, detail="Evidence photo not found.")
    if identity.role == "worker":
        worker = db.query(models.WorkerAccount.worker_id).filter_by(
            worker_id=identity.account_id,
            account_status="active",
        ).first()
        active_assignment = db.query(models.ComplaintAssignment.id).filter_by(
            id=update.assignment_id,
            worker_id=identity.account_id,
            active=True,
        ).first()
        if not worker or not active_assignment or update.worker_id != identity.account_id:
            raise HTTPException(status_code=404, detail="Evidence photo not found.")
    image_path = _safe_evidence_path(update.evidence_photo_path)
    if not image_path:
        raise HTTPException(status_code=404, detail="Evidence photo not found.")
    return FileResponse(image_path)
