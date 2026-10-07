from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Literal
from datetime import datetime

class ComplaintCreate(BaseModel):
    description: Optional[str] = None
    latitude: float
    longitude: float
    auto_detect: bool = True
    manual_type: Optional[str] = None  # used if auto_detect false or low confidence

class ComplaintOut(BaseModel):
    id: int
    image_url: str = Field(..., description="URL to the uploaded image")
    description: Optional[str]
    problem_type: str
    # AI image-classification confidence. None when the problem type was NOT set by the AI
    # (manual selection, description keywords, or fallback). Stored as 0.0 in the DB.
    confidence: Optional[float] = None
    ai_detected: bool = False
    severity: str
    latitude: float
    longitude: float
    area: Optional[str]
    timestamp: datetime
    status: str
    priority_score: Optional[float]
    cluster_id: Optional[int]

    @model_validator(mode="after")
    def _confidence_semantics(self):
        self.ai_detected = bool(self.confidence)
        if not self.confidence:
            self.confidence = None
        return self

    class Config:
        orm_mode = True

class ComplaintAdminOut(ComplaintOut):
    citizen_id: Optional[str] = None
    citizen_name: Optional[str] = None
    citizen_email: Optional[str] = None
    citizen_phone: Optional[str] = None

class PublicComplaintOut(BaseModel):
    id: int
    problem_type: str
    severity: str
    latitude: float
    longitude: float
    area: Optional[str]
    timestamp: datetime
    status: str
    priority_score: Optional[float]
    cluster_id: Optional[int]

class ComplaintStatusUpdate(BaseModel):
    status: str

class WorkUpdateOut(BaseModel):
    id: int
    complaint_id: int
    status: str
    message: Optional[str] = None
    updated_by: str
    uploaded_at: datetime
    photo_url: Optional[str] = None
    file_hash: Optional[str] = None
    authenticity_status: str
    metadata_summary: Optional[str] = None


class ResolutionConfirmationIn(BaseModel):
    response: Literal["confirmed", "unresolved"]


class ResolutionConfirmationEventOut(BaseModel):
    id: int
    resolution_update_id: int
    citizen_id: Optional[str] = None
    response: Literal["confirmed", "unresolved"]
    created_at: datetime


class ResolutionConfirmationOut(BaseModel):
    complaint_id: int
    complaint_status: str
    resolution_update_id: Optional[int] = None
    resolution_status: str
    can_respond: bool
    resolved_at: Optional[datetime] = None
    resolution_message: Optional[str] = None
    completion_photo_url: Optional[str] = None
    citizen_photo_url: Optional[str] = None
    citizen_photo_uploaded_at: Optional[datetime] = None
    citizen_photo_file_hash: Optional[str] = None
    citizen_photo_authenticity_status: Optional[str] = None
    citizen_photo_metadata_summary: Optional[str] = None
    response: Optional[Literal["confirmed", "unresolved"]] = None
    responded_at: Optional[datetime] = None
    history: List[ResolutionConfirmationEventOut] = Field(default_factory=list)

class DashboardSummary(BaseModel):
    total_complaints: int
    high_severity: int
    medium_severity: int
    low_severity: int

class AreaStats(BaseModel):
    area: str
    total: int
    high_severity: int
    medium_severity: int
    low_severity: int
    potholes: int
    garbage: int
    streetlights: int
    drainage: int
    damaged_roads: int
    hotspots: int
    score: float
    status: str


class ImpactPriorityOut(BaseModel):
    complaint_id: int
    legacy_priority_score: Optional[float] = None
    impact_priority_score: Optional[int] = None
    severity: str
    severity_score: int
    exposure_score: Optional[int] = None
    recurrence_count: int
    recurrence_score: int
    nearby_schools: Optional[int] = None
    nearby_hospitals: Optional[int] = None
    nearby_clinics: Optional[int] = None
    nearby_bus_stops: Optional[int] = None
    nearby_major_roads: Optional[int] = None
    major_road_proximity: Optional[bool] = None
    osm_status: str
    osm_error_code: Optional[str] = None
    osm_cache_hit: bool
    osm_fetched_at: Optional[datetime] = None
    osm_radius_m: int
    recurrence_radius_m: int
    recurrence_window_days: int
    formula: str
    component_methodology: str
    explanation: str
    fallback_reason: Optional[str] = None
    attribution: str


class WorkerCreateIn(BaseModel):
    worker_id: str = Field(min_length=3, max_length=32)
    full_name: str = Field(min_length=2, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=30)
    department: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class WorkerAccountStatusIn(BaseModel):
    account_status: Literal["active", "suspended"]


class ComplaintAssignmentIn(BaseModel):
    worker_id: str = Field(min_length=3, max_length=32)
    deadline: Optional[datetime] = None
    note: Optional[str] = Field(default=None, max_length=1000)


class WorkVerificationIn(BaseModel):
    note: Optional[str] = Field(default=None, max_length=2000)
