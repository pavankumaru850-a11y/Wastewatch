"""schemas.py -- Pydantic v2 request/response models."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict, Field

from .models import RoleEnum, ReportStatus, PriorityEnum, VerificationStatusEnum


# ---------- auth ----------
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone: Optional[str] = None
    village: Optional[str] = None
    district: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    phone: Optional[str] = None
    role: RoleEnum
    village: Optional[str] = None
    district: Optional[str] = None
    is_active: bool
    created_at: datetime


# ---------- detection ----------
class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class DetectionOut(BaseModel):
    class_name: str
    confidence: float
    confidence_level: Optional[str] = None
    bbox: list[float]
    box: BoundingBox


class DetectionResponse(BaseModel):
    success: bool
    detected: bool = False
    is_waste: Optional[bool] = None  # True waste / False not waste / None AI unavailable
    code: Optional[str] = None
    message: Optional[str] = None
    detections: list[DetectionOut] = []
    object_count: int = 0
    model_version: Optional[str] = None
    confidence_level: Optional[str] = None
    severity: Optional[str] = None
    severity_score: Optional[float] = None
    priority_score: Optional[float] = None
    priority_level: Optional[str] = None
    quality: Optional[dict] = None


# ---------- reports ----------
class DetectionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float


class AssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    staff_id: int
    assigned_by: int
    assigned_at: datetime
    completed_at: Optional[datetime] = None
    remarks: Optional[str] = None


class CompletionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    report_id: int
    staff_id: int
    completion_image: str
    remarks: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    completed_at: datetime


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    image_path: str
    waste_type: Optional[str] = None
    confidence: Optional[float] = None
    is_waste: Optional[bool] = None
    latitude: float
    longitude: float
    address: Optional[str] = None
    village: Optional[str] = None
    district: Optional[str] = None
    description: Optional[str] = None
    status: ReportStatus
    priority: PriorityEnum
    severity_score: Optional[float] = None
    deadline: Optional[datetime] = None
    is_duplicate: bool = False
    duplicate_of_id: Optional[int] = None
    gps_accuracy: Optional[float] = None
    town: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    severity: Optional[str] = None
    priority_score: Optional[float] = None
    object_count: int = 0
    detection_summary: Optional[str] = None
    model_version: Optional[str] = None
    confidence_level: Optional[str] = None
    is_possible_duplicate: bool = False
    hotspot_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    detections: list[DetectionItemOut] = []
    assignment: Optional[AssignmentOut] = None
    completion: Optional[CompletionOut] = None


class ReclassifyRequest(BaseModel):
    is_waste: bool
    remarks: Optional[str] = None


class ReportUpdateRequest(BaseModel):
    status: Optional[ReportStatus] = None
    priority: Optional[PriorityEnum] = None
    description: Optional[str] = None
    address: Optional[str] = None
    village: Optional[str] = None
    district: Optional[str] = None


class AssignRequest(BaseModel):
    staff_id: int
    remarks: Optional[str] = None


class StatusUpdateRequest(BaseModel):
    status: ReportStatus
    remarks: Optional[str] = None


class VerificationRequest(BaseModel):
    verification_status: VerificationStatusEnum
    verified_class: Optional[str] = None
    remarks: Optional[str] = None


# ---------- dashboard ----------
class DashboardStats(BaseModel):
    total_reports: int
    new: int
    verified: int
    assigned: int
    in_progress: int
    completed: int
    rejected: int
    critical: int


# ---------- training ----------
class ModelVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    model_name: str
    version: str
    path: str
    precision: Optional[float] = None
    recall: Optional[float] = None
    map50: Optional[float] = None
    map5095: Optional[float] = None
    top1_accuracy: Optional[float] = None
    top5_accuracy: Optional[float] = None
    classes: Optional[list[str]] = None
    trained_at: Optional[datetime] = None
    deployed: bool
    notes: Optional[str] = None


# ---------- audit log ----------
class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    action: str
    report_id: Optional[int] = None
    details: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime


# ---------- waste types ----------
class WasteTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    label: Optional[str] = None
    is_active: bool


class WasteTypeCreate(BaseModel):
    name: str
    label: Optional[str] = None


# ---------- profile ----------
class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    village: Optional[str] = None
    district: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# ---------- v2 ----------
class HotspotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    latitude: float
    longitude: float
    total_reports: int
    cleanup_count: int
    dominant_waste_type: Optional[str] = None
    severity: str
    priority_score: float
    first_report_at: Optional[datetime] = None
    last_report_at: Optional[datetime] = None
    current_status: str
    color: Optional[str] = None


class DuplicateCheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    report_id: int
    candidate_id: int
    distance_m: Optional[float] = None
    hash_distance: Optional[int] = None
    time_diff_minutes: Optional[float] = None
    same_category: bool
    decision: str
    decided_by: Optional[int] = None
    decided_at: Optional[datetime] = None


class DuplicateDecision(BaseModel):
    decision: str  # CONFIRMED | NOT_DUPLICATE | MERGED


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    body: Optional[str] = None
    kind: Optional[str] = None
    report_id: Optional[int] = None
    is_read: bool
    created_at: datetime


class CleanupVerificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    report_id: int
    before_image: Optional[str] = None
    after_image: Optional[str] = None
    before_detection_count: Optional[int] = None
    after_detection_count: Optional[int] = None
    improvement_percentage: Optional[float] = None
    analysis_available: bool
    verified_by: Optional[int] = None
    verified_at: Optional[datetime] = None
    remarks: Optional[str] = None


class CleanupDecision(BaseModel):
    approve: bool
    remarks: Optional[str] = None


class AdminCreateUser(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: RoleEnum
    phone: Optional[str] = None
    village: Optional[str] = None
    district: Optional[str] = None


class AdminUpdateUser(BaseModel):
    role: Optional[RoleEnum] = None
    is_active: Optional[bool] = None
    name: Optional[str] = None
