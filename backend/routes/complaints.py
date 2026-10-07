from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import os
import shutil
import uuid
import hashlib
import json
from datetime import datetime, timezone
from io import BytesIO
from typing import List, Optional

from ..database import get_db, Base, engine, ensure_complaint_identity_column
from ..auth import PortalIdentity, get_current_user, require_roles
from .. import models, schemas
from ..services import ai_service, nlp_service, severity_service, area_service, clustering_service, priority_service

router = APIRouter()

# Create new tables when needed, then add only the nullable ownership column to
# an existing SQLite database. Existing complaints stay unassigned (NULL).
Base.metadata.create_all(bind=engine)
ensure_complaint_identity_column()

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'uploads'))
os.makedirs(UPLOAD_DIR, exist_ok=True)
EVIDENCE_UPLOAD_DIR = os.path.join(UPLOAD_DIR, 'authority_evidence')
os.makedirs(EVIDENCE_UPLOAD_DIR, exist_ok=True)
CITIZEN_EVIDENCE_UPLOAD_DIR = os.path.join(UPLOAD_DIR, 'citizen_resolution_evidence')
os.makedirs(CITIZEN_EVIDENCE_UPLOAD_DIR, exist_ok=True)
MAX_EVIDENCE_IMAGE_BYTES = 10 * 1024 * 1024


def _inspect_evidence_image(data: bytes):
    """Validate an original image and return safe provenance metadata, without re-encoding it."""
    signatures = {
        'PNG': (data.startswith(b'\x89PNG\r\n\x1a\n'), '.png'),
        'JPEG': (data.startswith(b'\xff\xd8\xff'), '.jpg'),
        'WEBP': (len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WEBP', '.webp'),
    }
    detected = next((name for name, (matches, _) in signatures.items() if matches), None)
    if not detected:
        raise HTTPException(status_code=400, detail='Upload a valid JPG, PNG, or WEBP image.')

    try:
        from PIL import ExifTags, Image
        with Image.open(BytesIO(data)) as image:
            image.verify()
        with Image.open(BytesIO(data)) as image:
            image_format = (image.format or '').upper()
            width, height = image.size
            exif = image.getexif()
            exif_names = sorted({ExifTags.TAGS.get(key, str(key)) for key in exif.keys()})
            exif_values = ' '.join(str(value) for value in exif.values()).lower()
        if image_format != detected or image_format not in signatures:
            raise ValueError('Image signature and decoded format differ.')
        if width <= 0 or height <= 0 or width * height > 40_000_000:
            raise ValueError('Image dimensions are outside the allowed range.')
    except Exception as exc:
        raise HTTPException(status_code=400, detail='The uploaded file is not a valid supported image.') from exc

    lower_bytes = data.lower()
    c2pa_detected = any(marker in lower_bytes for marker in (b'c2pa', b'content credentials', b'contentcredentials'))
    scan_text = lower_bytes + exif_values.encode('utf-8', errors='ignore')
    known_ai_markers = (
        b'midjourney', b'stable diffusion', b'stable-diffusion', b'dall-e', b'openai',
        b'adobe firefly', b'generative fill', b'ai-generated', b'ai generated',
        b'comfyui', b'automatic1111',
    )
    ai_indicators = [marker.decode('ascii') for marker in known_ai_markers if marker in scan_text]

    if ai_indicators:
        authenticity_status = 'Known AI-generation metadata indicator(s) detected; this heuristic does not prove image origin.'
    elif c2pa_detected:
        authenticity_status = 'Content Credentials/C2PA marker detected; cryptographic provenance was not verified.'
    else:
        authenticity_status = 'No known AI-generation metadata detected; this is not proof the image is not AI-generated.'

    metadata_summary = json.dumps({
        'format': image_format,
        'dimensions': [width, height],
        'exif_tag_names': exif_names[:30],
        'c2pa_marker_detected': c2pa_detected,
        'ai_metadata_indicators': ai_indicators,
        'inspection_note': 'Heuristic metadata inspection only; no cryptographic provenance verification.',
    }, separators=(',', ':'))
    return signatures[image_format][1], hashlib.sha256(data).hexdigest(), authenticity_status, metadata_summary


def _work_update_out(update: models.ComplaintWorkUpdate):
    return schemas.WorkUpdateOut(
        id=update.id,
        complaint_id=update.complaint_id,
        status=update.status,
        message=update.message,
        updated_by='Admin',
        uploaded_at=update.uploaded_at,
        photo_url=f'/api/complaints/work-updates/{update.id}/photo' if update.photo_path else None,
        file_hash=update.file_hash,
        authenticity_status=update.authenticity_status,
        metadata_summary=update.metadata_summary,
    )


def _safe_upload_path(upload_dir: str, photo_name: Optional[str]):
    if not photo_name:
        return None
    upload_root = os.path.normcase(os.path.realpath(upload_dir))
    image_path = os.path.normcase(os.path.realpath(os.path.join(upload_dir, photo_name)))
    try:
        is_within_upload_root = os.path.commonpath([upload_root, image_path]) == upload_root
    except ValueError:
        is_within_upload_root = False
    return image_path if is_within_upload_root and os.path.isfile(image_path) else None


def _safe_evidence_path(photo_name: Optional[str]):
    return _safe_upload_path(EVIDENCE_UPLOAD_DIR, photo_name)


def _safe_citizen_evidence_path(photo_name: Optional[str]):
    return _safe_upload_path(CITIZEN_EVIDENCE_UPLOAD_DIR, photo_name)


def _resolution_confirmation_out(db: Session, complaint: models.Complaint, *, admin: bool):
    latest_resolution = db.query(models.ComplaintWorkUpdate).filter(
        models.ComplaintWorkUpdate.complaint_id == complaint.id,
        models.ComplaintWorkUpdate.status == 'Resolved',
    ).order_by(models.ComplaintWorkUpdate.id.desc()).first()
    safe_photo = _safe_evidence_path(latest_resolution.photo_path) if latest_resolution else None
    current_response = None
    citizen_evidence = None
    if latest_resolution and complaint.citizen_id:
        current_response = db.query(models.CitizenResolutionConfirmation).filter_by(
            complaint_id=complaint.id,
            resolution_update_id=latest_resolution.id,
            citizen_id=complaint.citizen_id,
        ).first()
        citizen_evidence = db.query(models.CitizenResolutionEvidence).filter_by(
            complaint_id=complaint.id,
            resolution_update_id=latest_resolution.id,
            citizen_id=complaint.citizen_id,
        ).first()
    safe_citizen_photo = _safe_citizen_evidence_path(citizen_evidence.photo_path) if citizen_evidence else None

    if latest_resolution is None or not complaint.citizen_id:
        resolution_status = 'not_available'
    elif current_response:
        resolution_status = current_response.response
    elif not safe_photo:
        resolution_status = 'evidence_unavailable' if complaint.status == 'Resolved' else 'not_pending'
    elif complaint.status == 'Resolved':
        resolution_status = 'awaiting'
    else:
        resolution_status = 'not_pending'

    history_query = db.query(models.CitizenResolutionConfirmation).filter_by(complaint_id=complaint.id)
    if not admin:
        history_query = history_query.filter_by(citizen_id=complaint.citizen_id)
    history_rows = history_query.order_by(models.CitizenResolutionConfirmation.id).all()
    return schemas.ResolutionConfirmationOut(
        complaint_id=complaint.id,
        complaint_status=complaint.status,
        resolution_update_id=latest_resolution.id if latest_resolution else None,
        resolution_status=resolution_status,
        can_respond=resolution_status == 'awaiting',
        resolved_at=latest_resolution.uploaded_at if latest_resolution else None,
        resolution_message=latest_resolution.message if latest_resolution else None,
        completion_photo_url=(f'/api/complaints/work-updates/{latest_resolution.id}/photo' if safe_photo and latest_resolution else None),
        citizen_photo_url=(f'/api/complaints/resolution-evidence/{citizen_evidence.id}/photo' if safe_citizen_photo and citizen_evidence else None),
        citizen_photo_uploaded_at=citizen_evidence.uploaded_at if safe_citizen_photo and citizen_evidence else None,
        citizen_photo_file_hash=citizen_evidence.file_hash if safe_citizen_photo and citizen_evidence else None,
        citizen_photo_authenticity_status=citizen_evidence.authenticity_status if safe_citizen_photo and citizen_evidence else None,
        citizen_photo_metadata_summary=citizen_evidence.metadata_summary if safe_citizen_photo and citizen_evidence else None,
        response=current_response.response if current_response else None,
        responded_at=current_response.created_at if current_response else None,
        history=[schemas.ResolutionConfirmationEventOut(
            id=event.id,
            resolution_update_id=event.resolution_update_id,
            citizen_id=event.citizen_id if admin else None,
            response=event.response,
            created_at=event.created_at,
        ) for event in history_rows],
    )


def _complaint_out(complaint: models.Complaint, *, admin: bool = False, citizen_account=None):
    values = dict(
        id=complaint.id,
        image_url=f'/api/complaints/{complaint.id}/image',
        description=complaint.description,
        problem_type=complaint.problem_type,
        confidence=complaint.confidence,
        severity=complaint.severity,
        latitude=complaint.latitude,
        longitude=complaint.longitude,
        area=complaint.area,
        timestamp=complaint.timestamp,
        status=complaint.status,
        priority_score=complaint.priority_score,
        cluster_id=complaint.cluster_id,
    )
    if admin:
        return schemas.ComplaintAdminOut(
            **values,
            citizen_id=complaint.citizen_id,
            citizen_name=citizen_account.full_name if citizen_account else None,
            citizen_email=citizen_account.email if citizen_account else None,
            citizen_phone=citizen_account.phone if citizen_account else None,
        )
    return schemas.ComplaintOut(**values)


@router.post('/', response_model=schemas.ComplaintOut, status_code=status.HTTP_201_CREATED)
async def create_complaint(
    image: UploadFile = File(...),
    description: Optional[str] = Form(None),
    latitude: float = Form(...),
    longitude: float = Form(...),
    auto_detect: bool = Form(True),
    manual_type: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: PortalIdentity = Depends(require_roles('citizen')),
):
    if image.content_type and not image.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail='Invalid image type')
    file_ext = os.path.splitext(image.filename or '')[1]
    unique_name = f'{uuid.uuid4()}{file_ext}'
    file_path = os.path.join(UPLOAD_DIR, unique_name)
    with open(file_path, 'wb') as buffer:
        shutil.copyfileobj(image.file, buffer)

    try:
        ai_result = ai_service.analyze_image(file_path)
    except Exception:
        ai_result = {'problem_type': 'Other', 'confidence': 0.0, 'severity': 'LOW'}
    nlp_result = nlp_service.analyze_text(description or '')

    problem_type = None
    confidence = 0.0
    if auto_detect and ai_result['confidence'] >= 0.6:
        problem_type = ai_result['problem_type']
        confidence = ai_result['confidence']
    elif manual_type:
        problem_type = manual_type
    elif nlp_result.get('problem_type'):
        problem_type = nlp_result['problem_type']
    else:
        problem_type = 'Other'

    severity = severity_service.determine_severity(ai_result.get('confidence', 0.0), nlp_result)
    area = area_service.get_area(latitude, longitude)
    complaint = models.Complaint(
        image_path=unique_name,
        description=description,
        problem_type=problem_type,
        confidence=confidence,
        severity=severity,
        latitude=latitude,
        longitude=longitude,
        area=area,
        status='Reported',
        citizen_id=current_user.account_id,
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)

    # Preserve the existing DBSCAN and stored-priority processing pipeline.
    clustering_service.update_clusters(db)
    complaint.priority_score = priority_service.compute_individual_score(db, complaint)
    db.commit()
    db.refresh(complaint)
    return _complaint_out(complaint)


@router.get('/', response_model=None)
async def list_complaints(
    status: Optional[str] = None,
    area: Optional[str] = None,
    problem_type: Optional[str] = None,
    ids: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: PortalIdentity = Depends(get_current_user),
):
    query = db.query(models.Complaint)
    if current_user.role == 'citizen':
        query = query.filter(models.Complaint.citizen_id == current_user.account_id)
    elif current_user.role == 'worker':
        worker = db.query(models.WorkerAccount).filter_by(
            worker_id=current_user.account_id,
            account_status='active',
        ).first()
        if not worker:
            raise HTTPException(status_code=403, detail='This worker account is inactive.')
        assigned_ids = db.query(models.ComplaintAssignment.complaint_id).filter_by(
            worker_id=current_user.account_id,
            active=True,
        ).distinct()
        query = query.filter(models.Complaint.id.in_(assigned_ids))
    if status:
        query = query.filter(models.Complaint.status == status)
    if area:
        query = query.filter(models.Complaint.area == area)
    if problem_type:
        query = query.filter(models.Complaint.problem_type == problem_type)
    if ids is not None:
        query = query.filter(models.Complaint.id.in_(ids))
    complaints = query.order_by(models.Complaint.id).all()
    if current_user.role != 'admin':
        return [_complaint_out(complaint) for complaint in complaints]
    citizen_ids = {complaint.citizen_id for complaint in complaints if complaint.citizen_id}
    accounts = db.query(models.CitizenAccount).filter(models.CitizenAccount.citizen_id.in_(citizen_ids)).all() if citizen_ids else []
    accounts_by_id = {account.citizen_id: account for account in accounts}
    return [
        _complaint_out(complaint, admin=True, citizen_account=accounts_by_id.get(complaint.citizen_id))
        for complaint in complaints
    ]


@router.get('/public', response_model=List[schemas.PublicComplaintOut])
async def list_public_map_complaints(
    db: Session = Depends(get_db),
    _identity: PortalIdentity = Depends(require_roles('citizen', 'admin')),
):
    # Whitelisted map fields only: no citizen ID, free-text description, image,
    # or AI confidence is returned to the citizen-facing map.
    complaints = db.query(models.Complaint).order_by(models.Complaint.id).all()
    return [schemas.PublicComplaintOut(
        id=c.id,
        problem_type=c.problem_type,
        severity=c.severity,
        latitude=c.latitude,
        longitude=c.longitude,
        area=c.area,
        timestamp=c.timestamp,
        status=c.status,
        priority_score=c.priority_score,
        cluster_id=c.cluster_id,
    ) for c in complaints]


@router.get('/{complaint_id}/work-updates', response_model=List[schemas.WorkUpdateOut])
async def list_work_updates(
    complaint_id: int,
    db: Session = Depends(get_db),
    current_user: PortalIdentity = Depends(require_roles('citizen', 'admin')),
):
    complaint = db.query(models.Complaint).filter(models.Complaint.id == complaint_id).first()
    if not complaint or (current_user.role == 'citizen' and complaint.citizen_id != current_user.account_id):
        raise HTTPException(status_code=404, detail='Complaint not found')
    updates = db.query(models.ComplaintWorkUpdate).filter(
        models.ComplaintWorkUpdate.complaint_id == complaint_id
    ).order_by(models.ComplaintWorkUpdate.id).all()
    return [_work_update_out(update) for update in updates]


@router.get('/{complaint_id}/resolution-confirmation', response_model=schemas.ResolutionConfirmationOut)
async def get_resolution_confirmation(
    complaint_id: int,
    db: Session = Depends(get_db),
    current_user: PortalIdentity = Depends(require_roles('citizen', 'admin')),
):
    complaint = db.query(models.Complaint).filter(models.Complaint.id == complaint_id).first()
    if not complaint or (current_user.role == 'citizen' and complaint.citizen_id != current_user.account_id):
        raise HTTPException(status_code=404, detail='Complaint not found')
    return _resolution_confirmation_out(db, complaint, admin=current_user.role == 'admin')


@router.post('/{complaint_id}/resolution-confirmation', response_model=schemas.ResolutionConfirmationOut, status_code=status.HTTP_201_CREATED)
async def submit_resolution_confirmation(
    complaint_id: int,
    payload: schemas.ResolutionConfirmationIn,
    db: Session = Depends(get_db),
    current_user: PortalIdentity = Depends(require_roles('citizen')),
):
    complaint = db.query(models.Complaint).filter(models.Complaint.id == complaint_id).first()
    if not complaint or complaint.citizen_id != current_user.account_id:
        raise HTTPException(status_code=404, detail='Complaint not found')
    if complaint.status != 'Resolved':
        raise HTTPException(status_code=409, detail='Only a currently resolved complaint can be confirmed.')

    resolution_update = db.query(models.ComplaintWorkUpdate).filter(
        models.ComplaintWorkUpdate.complaint_id == complaint.id,
        models.ComplaintWorkUpdate.status == 'Resolved',
    ).order_by(models.ComplaintWorkUpdate.id.desc()).first()
    if not resolution_update or not _safe_evidence_path(resolution_update.photo_path):
        raise HTTPException(status_code=409, detail='Current resolution evidence is unavailable; contact the authority.')
    existing = db.query(models.CitizenResolutionConfirmation).filter_by(
        resolution_update_id=resolution_update.id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail='A response has already been recorded for this resolution cycle.')

    confirmation = models.CitizenResolutionConfirmation(
        complaint_id=complaint.id,
        resolution_update_id=resolution_update.id,
        citizen_id=current_user.account_id,
        response=payload.response,
        created_at=datetime.now(timezone.utc),
    )
    db.add(confirmation)
    if payload.response == 'unresolved':
        complaint.status = 'Under Review'
    try:
        db.commit()
        db.refresh(confirmation)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail='A response has already been recorded for this resolution cycle.') from exc
    return _resolution_confirmation_out(db, complaint, admin=False)


@router.post('/{complaint_id}/resolution-confirmation/evidence', response_model=schemas.ResolutionConfirmationOut, status_code=status.HTTP_201_CREATED)
async def upload_citizen_resolution_evidence(
    complaint_id: int,
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: PortalIdentity = Depends(require_roles('citizen')),
):
    complaint = db.query(models.Complaint).filter(models.Complaint.id == complaint_id).first()
    if not complaint or complaint.citizen_id != current_user.account_id:
        raise HTTPException(status_code=404, detail='Complaint not found')
    if complaint.status != 'Resolved':
        raise HTTPException(status_code=409, detail='A photo can only be uploaded while this resolution is awaiting your response.')

    resolution_update = db.query(models.ComplaintWorkUpdate).filter(
        models.ComplaintWorkUpdate.complaint_id == complaint.id,
        models.ComplaintWorkUpdate.status == 'Resolved',
    ).order_by(models.ComplaintWorkUpdate.id.desc()).first()
    if not resolution_update or not _safe_evidence_path(resolution_update.photo_path):
        raise HTTPException(status_code=409, detail='Current authority completion evidence is unavailable.')
    existing_response = db.query(models.CitizenResolutionConfirmation).filter_by(
        resolution_update_id=resolution_update.id,
    ).first()
    if existing_response:
        raise HTTPException(status_code=409, detail='This resolution cycle has already been answered.')
    citizen_evidence = db.query(models.CitizenResolutionEvidence).filter_by(
        resolution_update_id=resolution_update.id,
        citizen_id=current_user.account_id,
    ).first()
    if citizen_evidence and _safe_citizen_evidence_path(citizen_evidence.photo_path):
        raise HTTPException(status_code=409, detail='A photo has already been uploaded for this resolution cycle.')

    content = await photo.read(MAX_EVIDENCE_IMAGE_BYTES + 1)
    if len(content) > MAX_EVIDENCE_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail='Evidence photos must be 10 MB or smaller.')
    if not content:
        raise HTTPException(status_code=400, detail='The selected evidence photo is empty.')
    extension, file_hash, authenticity_status, metadata_summary = _inspect_evidence_image(content)
    photo_name = f'{uuid.uuid4().hex}{extension}'
    saved_path = os.path.join(CITIZEN_EVIDENCE_UPLOAD_DIR, photo_name)
    try:
        with open(saved_path, 'xb') as image_file:
            image_file.write(content)
    except OSError as exc:
        raise HTTPException(status_code=500, detail='Could not store the citizen evidence photo.') from exc

    if citizen_evidence:
        citizen_evidence.photo_path = photo_name
        citizen_evidence.uploaded_at = datetime.now(timezone.utc)
        citizen_evidence.file_hash = file_hash
        citizen_evidence.authenticity_status = authenticity_status
        citizen_evidence.metadata_summary = metadata_summary
    else:
        citizen_evidence = models.CitizenResolutionEvidence(
            complaint_id=complaint.id,
            resolution_update_id=resolution_update.id,
            citizen_id=current_user.account_id,
            photo_path=photo_name,
            uploaded_at=datetime.now(timezone.utc),
            file_hash=file_hash,
            authenticity_status=authenticity_status,
            metadata_summary=metadata_summary,
        )
        db.add(citizen_evidence)
    try:
        db.commit()
        db.refresh(citizen_evidence)
    except IntegrityError as exc:
        db.rollback()
        if os.path.isfile(saved_path):
            os.remove(saved_path)
        raise HTTPException(status_code=409, detail='A photo has already been uploaded for this resolution cycle.') from exc
    except Exception as exc:
        db.rollback()
        if os.path.isfile(saved_path):
            os.remove(saved_path)
        raise HTTPException(status_code=500, detail='Could not save the citizen evidence photo.') from exc
    return _resolution_confirmation_out(db, complaint, admin=False)


@router.post('/{complaint_id}/work-updates', response_model=schemas.WorkUpdateOut, status_code=status.HTTP_201_CREATED)
async def create_work_update(
    complaint_id: int,
    work_status: str = Form(..., alias='status'),
    message: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    admin: PortalIdentity = Depends(require_roles('admin')),
):
    complaint = db.query(models.Complaint).filter(models.Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail='Complaint not found')
    if work_status not in {'In Progress', 'Resolved'}:
        raise HTTPException(status_code=400, detail='Work updates support In Progress or Resolved status only.')
    message = (message or '').strip() or None
    if message and len(message) > 2000:
        raise HTTPException(status_code=400, detail='The authority message must be 2,000 characters or fewer.')
    if work_status == 'Resolved' and photo is None:
        raise HTTPException(status_code=400, detail='A completion photo is required before resolving this complaint.')

    photo_name = None
    file_hash = None
    metadata_summary = None
    authenticity_status = 'No photo uploaded; no authenticity check performed.'
    saved_path = None
    if photo is not None:
        content = await photo.read(MAX_EVIDENCE_IMAGE_BYTES + 1)
        if len(content) > MAX_EVIDENCE_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail='Evidence photos must be 10 MB or smaller.')
        if not content:
            raise HTTPException(status_code=400, detail='The selected evidence photo is empty.')
        extension, file_hash, authenticity_status, metadata_summary = _inspect_evidence_image(content)
        photo_name = f'{uuid.uuid4().hex}{extension}'
        saved_path = os.path.join(EVIDENCE_UPLOAD_DIR, photo_name)
        try:
            with open(saved_path, 'xb') as image_file:
                image_file.write(content)
        except OSError as exc:
            raise HTTPException(status_code=500, detail='Could not store the evidence photo.') from exc

    update = models.ComplaintWorkUpdate(
        complaint_id=complaint.id,
        status=work_status,
        message=message,
        photo_path=photo_name,
        uploaded_by=admin.account_id,
        uploaded_at=datetime.now(timezone.utc),
        file_hash=file_hash,
        authenticity_status=authenticity_status,
        metadata_summary=metadata_summary,
    )
    complaint.status = work_status
    db.add(update)
    try:
        db.commit()
        db.refresh(update)
    except Exception as exc:
        db.rollback()
        if saved_path and os.path.isfile(saved_path):
            os.remove(saved_path)
        raise HTTPException(status_code=500, detail='Could not save the authority work update.') from exc
    return _work_update_out(update)


@router.get('/work-updates/{update_id}/photo')
async def get_work_update_photo(
    update_id: int,
    db: Session = Depends(get_db),
    current_user: PortalIdentity = Depends(require_roles('citizen', 'admin', 'worker')),
):
    update = db.query(models.ComplaintWorkUpdate).filter(models.ComplaintWorkUpdate.id == update_id).first()
    if not update or not update.photo_path:
        raise HTTPException(status_code=404, detail='Evidence photo not found')
    complaint = db.query(models.Complaint).filter(models.Complaint.id == update.complaint_id).first()
    if not complaint or (current_user.role == 'citizen' and complaint.citizen_id != current_user.account_id):
        raise HTTPException(status_code=404, detail='Evidence photo not found')
    if current_user.role == 'worker':
        active_worker = db.query(models.WorkerAccount.worker_id).filter_by(
            worker_id=current_user.account_id,
            account_status='active',
        ).first()
        assigned = db.query(models.ComplaintAssignment.id).filter_by(
            complaint_id=complaint.id,
            worker_id=current_user.account_id,
            active=True,
        ).first()
        if not active_worker or not assigned:
            raise HTTPException(status_code=404, detail='Evidence photo not found')
    image_path = _safe_evidence_path(update.photo_path)
    if not image_path:
        raise HTTPException(status_code=404, detail='Evidence photo not found')
    return FileResponse(image_path)


@router.get('/resolution-evidence/{evidence_id}/photo')
async def get_citizen_resolution_evidence_photo(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: PortalIdentity = Depends(require_roles('citizen', 'admin')),
):
    evidence = db.query(models.CitizenResolutionEvidence).filter(
        models.CitizenResolutionEvidence.id == evidence_id,
    ).first()
    complaint = db.query(models.Complaint).filter(
        models.Complaint.id == evidence.complaint_id,
    ).first() if evidence else None
    if not evidence or not complaint or evidence.citizen_id != complaint.citizen_id:
        raise HTTPException(status_code=404, detail='Evidence photo not found')
    if current_user.role == 'citizen' and current_user.account_id != evidence.citizen_id:
        raise HTTPException(status_code=404, detail='Evidence photo not found')
    image_path = _safe_citizen_evidence_path(evidence.photo_path)
    if not image_path:
        raise HTTPException(status_code=404, detail='Evidence photo not found')
    return FileResponse(image_path)


@router.get('/{complaint_id}/image')
async def get_complaint_image(
    complaint_id: int,
    db: Session = Depends(get_db),
    current_user: PortalIdentity = Depends(get_current_user),
):
    complaint = db.query(models.Complaint).filter(models.Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail='Complaint not found')
    if current_user.role == 'worker':
        active_worker = db.query(models.WorkerAccount.worker_id).filter_by(
            worker_id=current_user.account_id,
            account_status='active',
        ).first()
        assigned_worker = db.query(models.ComplaintAssignment.id).filter_by(
            complaint_id=complaint.id,
            worker_id=current_user.account_id,
            active=True,
        ).first()
        if not active_worker or not assigned_worker:
            raise HTTPException(status_code=404, detail='Complaint not found')
    elif current_user.role != 'admin' and complaint.citizen_id != current_user.account_id:
        raise HTTPException(status_code=404, detail='Complaint not found')
    upload_root = os.path.normcase(os.path.realpath(UPLOAD_DIR))
    image_path = os.path.normcase(os.path.realpath(os.path.join(UPLOAD_DIR, complaint.image_path)))
    try:
        is_within_upload_root = os.path.commonpath([upload_root, image_path]) == upload_root
    except ValueError:
        is_within_upload_root = False
    if not is_within_upload_root or not os.path.isfile(image_path):
        raise HTTPException(status_code=404, detail='Complaint image not found')
    return FileResponse(image_path)


@router.get('/{complaint_id}', response_model=None)
async def get_complaint(
    complaint_id: int,
    db: Session = Depends(get_db),
    current_user: PortalIdentity = Depends(get_current_user),
):
    complaint = db.query(models.Complaint).filter(models.Complaint.id == complaint_id).first()
    if not complaint or current_user.role not in {'admin', 'citizen'} or (
        current_user.role == 'citizen' and complaint.citizen_id != current_user.account_id
    ):
        raise HTTPException(status_code=404, detail='Complaint not found')
    citizen_account = None
    if current_user.role == 'admin' and complaint.citizen_id:
        citizen_account = db.query(models.CitizenAccount).filter_by(citizen_id=complaint.citizen_id).first()
    return _complaint_out(complaint, admin=current_user.role == 'admin', citizen_account=citizen_account)


@router.patch('/{complaint_id}', response_model=None)
async def update_status(
    complaint_id: int,
    payload: schemas.ComplaintStatusUpdate,
    db: Session = Depends(get_db),
    _identity: PortalIdentity = Depends(require_roles('admin')),
):
    complaint = db.query(models.Complaint).filter(models.Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail='Complaint not found')
    if payload.status not in {'Reported', 'Under Review', 'Assigned', 'In Progress', 'Resolved'}:
        raise HTTPException(status_code=400, detail='Invalid status')
    if payload.status == 'Resolved' and complaint.status != 'Resolved':
        resolution_evidence = db.query(models.ComplaintWorkUpdate).filter(
            models.ComplaintWorkUpdate.complaint_id == complaint_id,
            models.ComplaintWorkUpdate.status == 'Resolved',
            models.ComplaintWorkUpdate.photo_path.isnot(None),
        ).order_by(models.ComplaintWorkUpdate.id.desc()).first()
        if not resolution_evidence or not _safe_evidence_path(resolution_evidence.photo_path):
            raise HTTPException(status_code=400, detail='A completion photo is required before resolving this complaint.')
        answered_cycle = db.query(models.CitizenResolutionConfirmation).filter_by(
            resolution_update_id=resolution_evidence.id,
        ).first()
        if answered_cycle:
            raise HTTPException(status_code=409, detail='Submit a new resolution-evidence work update to start a new confirmation cycle.')
    complaint.status = payload.status
    db.commit()
    db.refresh(complaint)
    citizen_account = db.query(models.CitizenAccount).filter_by(citizen_id=complaint.citizen_id).first() if complaint.citizen_id else None
    return _complaint_out(complaint, admin=True, citizen_account=citizen_account)
