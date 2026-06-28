"""Typed domain values shared by API, persistence, and services."""

from enum import Enum


class CaptureSource(str, Enum):
    MOBILE = "mobile"
    DRONE = "drone"
    FIXED_CAMERA = "fixed_camera"
    MANUAL = "manual"


class IngestibleCaptureSource(str, Enum):
    MOBILE = "mobile"


class CaptureAngle(str, Enum):
    FRONT = "front"
    REAR = "rear"
    DRIVER_SIDE = "driver_side"
    PASSENGER_SIDE = "passenger_side"
    TOP = "top"
    UNDERCARRIAGE = "undercarriage"


class InspectionStatus(str, Enum):
    UPLOADING = "uploading"
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    COMPLETE = "complete"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"


class AnalysisJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class FindingType(str, Enum):
    DENT = "dent"
    SCRATCH = "scratch"
    CRACK = "crack"
    MISSING_COMPONENT = "missing_component"
    RUST = "rust"
    ANOMALY = "anomaly"


class FindingStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    CLEAR = "clear"


class FleetRole(str, Enum):
    VIEWER = "viewer"
    INSPECTOR = "inspector"
    ADMIN = "admin"
