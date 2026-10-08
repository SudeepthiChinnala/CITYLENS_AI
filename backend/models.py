from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, Text, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.sql import func
from .database import Base

class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    image_path = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    problem_type = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    severity = Column(Enum("LOW", "MEDIUM", "HIGH", name="severity_levels"), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    area = Column(String, nullable=True)  # will be filled by area_service
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(Enum("Reported", "Under Review", "Assigned", "In Progress", "Resolved", name="status_enum"), default="Reported", nullable=False)
    priority_score = Column(Float, nullable=True)
    cluster_id = Column(Integer, nullable=True)
    citizen_id = Column(String, nullable=True)


class CitizenAccount(Base):
    __tablename__ = "citizen_accounts"

    citizen_id = Column(String(32), primary_key=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(254, collation="NOCASE"), nullable=False, unique=True)
    phone = Column(String(30), nullable=True)
    password_hash = Column(String(256), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ComplaintWorkUpdate(Base):
    __tablename__ = "complaint_work_updates"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False, index=True)
    status = Column(String(30), nullable=False)
    message = Column(Text, nullable=True)
    photo_path = Column(String(80), nullable=True)
    uploaded_by = Column(String(128), nullable=False)
    uploaded_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    file_hash = Column(String(64), nullable=True)
    authenticity_status = Column(String(300), nullable=False)
    metadata_summary = Column(Text, nullable=True)


class OSMExposureCache(Base):
    __tablename__ = "osm_exposure_cache"

    cache_key = Column(String(64), primary_key=True)
    latitude_cell = Column(Float, nullable=False)
    longitude_cell = Column(Float, nullable=False)
    radius_m = Column(Integer, nullable=False)
    source_status = Column(String(24), nullable=False)
    counts_json = Column(Text, nullable=False)
    error_code = Column(String(40), nullable=True)
    fetched_at = Column(DateTime(timezone=True), nullable=False)


class CitizenResolutionEvidence(Base):
    """One citizen-uploaded photo for a specific authority resolution cycle."""
    __tablename__ = "citizen_resolution_evidence"
    __table_args__ = (UniqueConstraint("resolution_update_id", "citizen_id", name="uq_citizen_resolution_evidence_cycle_owner"),)

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False, index=True)
    resolution_update_id = Column(Integer, ForeignKey("complaint_work_updates.id"), nullable=False, index=True)
    citizen_id = Column(String(32), nullable=False, index=True)
    photo_path = Column(String(80), nullable=False)
    uploaded_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    file_hash = Column(String(64), nullable=False)
    authenticity_status = Column(String(300), nullable=False)
    metadata_summary = Column(Text, nullable=True)


class CitizenResolutionConfirmation(Base):
    """One immutable citizen response per authority resolution-evidence cycle."""
    __tablename__ = "citizen_resolution_confirmations"
    __table_args__ = (UniqueConstraint("resolution_update_id", name="uq_resolution_confirmation_cycle"),)

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False, index=True)
    # The resolved work-update row is the cycle identifier; a later resolution
    # creates a new work-update ID and can receive a new citizen response.
    resolution_update_id = Column(Integer, ForeignKey("complaint_work_updates.id"), nullable=False, index=True)
    citizen_id = Column(String(32), nullable=False, index=True)
    response = Column(String(16), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())


class WorkerAccount(Base):
    __tablename__ = "worker_accounts"

    worker_id = Column(String(32), primary_key=True)
    full_name = Column(String(120), nullable=False)
    phone = Column(String(30), nullable=True)
    department = Column(String(120), nullable=False)
    password_hash = Column(String(256), nullable=False)
    account_status = Column(String(16), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())


class ComplaintAssignment(Base):
    """Immutable assignment records; reassignment deactivates but never deletes history."""
    __tablename__ = "complaint_assignments"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False, index=True)
    worker_id = Column(String(32), ForeignKey("worker_accounts.worker_id"), nullable=False, index=True)
    assigned_by = Column(String(128), nullable=False)
    assigned_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    deadline = Column(DateTime(timezone=True), nullable=True)
    assignment_note = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True, index=True)
    status = Column(String(30), nullable=False, default="Assigned")
    progress_percentage = Column(Integer, nullable=False, default=0)


class WorkerProgressUpdate(Base):
    """Append-only worker status/progress history with evidence stored by the shared upload system."""
    __tablename__ = "worker_progress_updates"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False, index=True)
    assignment_id = Column(Integer, ForeignKey("complaint_assignments.id"), nullable=False, index=True)
    worker_id = Column(String(32), ForeignKey("worker_accounts.worker_id"), nullable=False, index=True)
    previous_status = Column(String(30), nullable=True)
    new_status = Column(String(30), nullable=False)
    progress_percentage = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    evidence_photo_path = Column(String(80), nullable=True)
    updated_by = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    file_hash = Column(String(64), nullable=True)
    authenticity_status = Column(String(300), nullable=False, default="No photo uploaded; no authenticity check performed.")
    metadata_summary = Column(Text, nullable=True)


class AdminAccount(Base):
    __tablename__ = "admin_accounts"

    admin_id = Column(String(32), primary_key=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(254), nullable=True)
    password_hash = Column(String(256), nullable=False)
    account_status = Column(String(16), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

