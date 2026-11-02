"""
models.py -- SQLAlchemy ORM models for every table in the spec:
users, waste_reports, detection_items, staff_assignments, verification,
completion_reports, training_images, model_versions.
"""
import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text
)
from sqlalchemy.orm import relationship

from .database import Base


class RoleEnum(str, enum.Enum):
    ADMIN = "ADMIN"
    STAFF = "STAFF"
    CITIZEN = "CITIZEN"


class ReportStatus(str, enum.Enum):
    NEW = "NEW"
    AI_DETECTED = "AI_DETECTED"
    STAFF_REVIEW = "STAFF_REVIEW"
    VERIFIED = "VERIFIED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    CLEANED = "CLEANED"
    CLEANUP_VERIFICATION = "CLEANUP_VERIFICATION"
    CLOSED = "CLOSED"
    COMPLETED = "COMPLETED"  # legacy value kept so existing rows/clients keep working
    REJECTED = "REJECTED"
    NOT_WASTE = "NOT_WASTE"  # AI decided the photo contains no waste: stored separately, never counted as waste


class PriorityEnum(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class VerificationStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    CORRECT = "CORRECT"
    INCORRECT = "INCORRECT"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(20), nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.CITIZEN)
    village = Column(String(120), nullable=True)
    district = Column(String(120), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    reports = relationship("WasteReport", back_populates="reporter", foreign_keys="WasteReport.user_id")
    assignments = relationship("StaffAssignment", back_populates="staff", foreign_keys="StaffAssignment.staff_id")


class WasteReport(Base):
    __tablename__ = "waste_reports"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    image_path = Column(String(500), nullable=False)
    waste_type = Column(String(80), nullable=True)
    confidence = Column(Float, nullable=True)
    is_waste = Column(Boolean, nullable=True)  # True = waste, False = not waste, None = AI could not decide (needs human review)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(String(500), nullable=True)
    village = Column(String(120), nullable=True)
    district = Column(String(120), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(Enum(ReportStatus), nullable=False, default=ReportStatus.NEW)
    priority = Column(Enum(PriorityEnum), nullable=False, default=PriorityEnum.MEDIUM)
    severity_score = Column(Float, nullable=True)  # 0-100, computed at creation; see report_service.compute_severity
    deadline = Column(DateTime, nullable=True)  # target cleanup time, derived from priority at creation
    is_duplicate = Column(Boolean, default=False)  # flagged, never auto-rejected -- staff still decide
    duplicate_of_id = Column(Integer, ForeignKey("waste_reports.id"), nullable=True)
    # --- v2 fields ---
    gps_accuracy = Column(Float, nullable=True)
    town = Column(String(120), nullable=True)
    state = Column(String(120), nullable=True)
    country = Column(String(120), nullable=True)
    image_hash = Column(String(32), nullable=True)
    severity = Column(String(16), nullable=True)          # LOW/MEDIUM/HIGH/CRITICAL
    priority_score = Column(Float, nullable=True)         # 0-100
    object_count = Column(Integer, default=0)
    detection_summary = Column(String(300), nullable=True)
    model_version = Column(String(40), nullable=True)
    confidence_level = Column(String(10), nullable=True)
    quality_ok = Column(Boolean, default=True)
    is_possible_duplicate = Column(Boolean, default=False)
    hotspot_id = Column(Integer, ForeignKey("hotspots.id"), nullable=True)
    client_uuid = Column(String(64), nullable=True, unique=True)  # offline-sync idempotency key
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_reports_lat_lng", "latitude", "longitude"),
        Index("ix_reports_status", "status"), Index("ix_reports_created", "created_at"),
        Index("ix_reports_severity", "severity"), Index("ix_reports_priority", "priority_score"),
        Index("ix_reports_waste", "waste_type"),
        Index("ix_reports_is_waste", "is_waste"),
    )
    reporter = relationship("User", back_populates="reports", foreign_keys=[user_id])
    detections = relationship("DetectionItem", back_populates="report", cascade="all, delete-orphan")
    assignment = relationship("StaffAssignment", back_populates="report", uselist=False, cascade="all, delete-orphan")
    verifications = relationship("Verification", back_populates="report", cascade="all, delete-orphan")
    completion = relationship("CompletionReport", back_populates="report", uselist=False, cascade="all, delete-orphan")


class DetectionItem(Base):
    __tablename__ = "detection_items"
    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("waste_reports.id"), nullable=False)
    class_name = Column(String(80), nullable=False)
    confidence = Column(Float, nullable=False)
    x1 = Column(Float, nullable=False)
    y1 = Column(Float, nullable=False)
    x2 = Column(Float, nullable=False)
    y2 = Column(Float, nullable=False)

    report = relationship("WasteReport", back_populates="detections")


class StaffAssignment(Base):
    __tablename__ = "staff_assignments"
    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("waste_reports.id"), nullable=False, unique=True)
    staff_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    remarks = Column(Text, nullable=True)

    report = relationship("WasteReport", back_populates="assignment")
    staff = relationship("User", back_populates="assignments", foreign_keys=[staff_id])


class Verification(Base):
    __tablename__ = "verification"
    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("waste_reports.id"), nullable=False)
    predicted_class = Column(String(80), nullable=True)
    verified_class = Column(String(80), nullable=True)
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    verification_status = Column(Enum(VerificationStatusEnum), default=VerificationStatusEnum.PENDING)
    remarks = Column(Text, nullable=True)
    verified_at = Column(DateTime, default=datetime.utcnow)

    report = relationship("WasteReport", back_populates="verifications")


class CompletionReport(Base):
    __tablename__ = "completion_reports"
    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("waste_reports.id"), nullable=False, unique=True)
    staff_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    completion_image = Column(String(500), nullable=False)
    remarks = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    completed_at = Column(DateTime, default=datetime.utcnow)

    report = relationship("WasteReport", back_populates="completion")


class TrainingImage(Base):
    __tablename__ = "training_images"
    id = Column(Integer, primary_key=True, index=True)
    image_path = Column(String(500), nullable=False)
    class_name = Column(String(80), nullable=False)
    annotation_path = Column(String(500), nullable=True)
    verified = Column(Boolean, default=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(120), nullable=False)
    version = Column(String(40), nullable=False)
    path = Column(String(500), nullable=False)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    map50 = Column(Float, nullable=True)
    map5095 = Column(Float, nullable=True)
    trained_at = Column(DateTime, nullable=True)
    dataset_version = Column(String(40), nullable=True)
    deployed = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)


class AuditLog(Base):
    """Append-only trail of who did what to which report -- assignment,
    status changes, verification, completion. Never edited or deleted,
    only inserted; see services/audit_service.py for the single write path."""
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(80), nullable=False)
    report_id = Column(Integer, ForeignKey("waste_reports.id"), nullable=True)
    details = Column(Text, nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class WasteType(Base):
    """Admin-configurable waste classes (spec section 2: 'make classes
    configurable so additional classes can be added later'). Seeded with
    the 4 initial classes on first startup -- see main.py."""
    __tablename__ = "waste_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(80), unique=True, nullable=False)
    label = Column(String(120), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------- v2 tables
class SystemSetting(Base):
    __tablename__ = "system_settings"
    key = Column(String(80), primary_key=True)
    value = Column(Text, nullable=False)  # JSON-encoded
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Hotspot(Base):
    __tablename__ = "hotspots"
    id = Column(Integer, primary_key=True, index=True)
    latitude = Column(Float, nullable=False)   # centroid
    longitude = Column(Float, nullable=False)
    total_reports = Column(Integer, default=0)
    cleanup_count = Column(Integer, default=0)
    dominant_waste_type = Column(String(80), nullable=True)
    severity = Column(String(16), default="LOW")
    priority_score = Column(Float, default=0.0)
    first_report_at = Column(DateTime, nullable=True)
    last_report_at = Column(DateTime, nullable=True)
    current_status = Column(String(30), default="ACTIVE")  # ACTIVE / CLEANED / MONITORING
    created_at = Column(DateTime, default=datetime.utcnow)


class DuplicateCheck(Base):
    """One row per (report, candidate) pair the system flagged. Staff decide;
    nothing is auto-deleted."""
    __tablename__ = "duplicate_checks"
    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("waste_reports.id"), nullable=False, index=True)
    candidate_id = Column(Integer, ForeignKey("waste_reports.id"), nullable=False)
    distance_m = Column(Float, nullable=True)
    hash_distance = Column(Integer, nullable=True)
    time_diff_minutes = Column(Float, nullable=True)
    same_category = Column(Boolean, default=False)
    decision = Column(String(20), default="PENDING")  # PENDING/CONFIRMED/NOT_DUPLICATE/MERGED
    decided_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    decided_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class StatusHistory(Base):
    __tablename__ = "status_history"
    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("waste_reports.id"), nullable=False, index=True)
    old_status = Column(String(30), nullable=True)
    new_status = Column(String(30), nullable=False)
    changed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(160), nullable=False)
    body = Column(Text, nullable=True)
    kind = Column(String(40), nullable=True)
    report_id = Column(Integer, ForeignKey("waste_reports.id"), nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class CleanupVerification(Base):
    """Before/after AI comparison for a completed cleanup."""
    __tablename__ = "cleanup_verifications"
    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("waste_reports.id"), nullable=False, unique=True)
    before_image = Column(String(500), nullable=True)
    after_image = Column(String(500), nullable=True)
    before_detection_count = Column(Integer, nullable=True)
    after_detection_count = Column(Integer, nullable=True)
    improvement_percentage = Column(Float, nullable=True)
    analysis_available = Column(Boolean, default=False)  # False if AI model was unavailable
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
