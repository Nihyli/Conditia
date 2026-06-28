"""Pydantic request/response models (API contract)."""

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from domain import (
    CaptureAngle,
    CaptureSource,
    FindingStatus,
    FindingType,
    IngestibleCaptureSource,
    InspectionStatus,
    Severity,
)


class TruckCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vin: str = Field(min_length=17, max_length=17, pattern=r"^[A-HJ-NPR-Z0-9]{17}$")
    make: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)
    year: int | None = Field(default=None, ge=1900)
    license_plate: str | None = Field(default=None, max_length=32)
    fleet_id: UUID | None = None

    @field_validator("vin", mode="before")
    @classmethod
    def normalize_vin(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("make", "model", "license_plate", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("year")
    @classmethod
    def validate_model_year(cls, value: int | None) -> int | None:
        if value is not None and value > datetime.now(timezone.utc).year + 1:
            raise ValueError("year cannot be more than one year in the future")
        return value


class TruckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    fleet_id: str | None
    vin: str
    make: str | None
    model: str | None
    year: int | None
    license_plate: str | None
    created_at: datetime


class InspectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    truck_id: UUID
    capture_source: IngestibleCaptureSource = IngestibleCaptureSource.MOBILE


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    inspection_id: str
    media_id: str | None
    title: str | None
    finding_type: FindingType
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    status: FindingStatus
    resolved_at: datetime | None
    resolution_notes: str | None
    zone: str | None = Field(default=None, max_length=64)
    location: str | None
    bounding_box: dict | None
    description: str | None
    annotated_image_path: str | None
    first_seen_inspection_id: str | None
    # 0 = new this inspection; N = first seen N inspections ago on this truck
    first_detected_inspections_ago: int = 0


class MediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    inspection_id: str
    media_type: str
    capture_angle: CaptureAngle | None
    capture_source: CaptureSource
    drone_flight_id: str | None
    captured_at: datetime


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    inspection_id: str
    generated_at: datetime
    summary: str | None
    total_findings: int
    critical_findings: int
    pdf_path: str | None
    raw_json: dict | None


class InspectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    truck_id: str
    started_at: datetime
    completed_at: datetime | None
    status: InspectionStatus
    capture_source: CaptureSource


class InspectionSummary(BaseModel):
    """Shape consumed by the dashboard's recent-inspections list + damage map."""

    id: str
    truck_id: str
    truck_label: str
    make: str | None
    model: str | None
    started_at: datetime
    status: InspectionStatus
    capture_source: CaptureSource
    finding_count: int
    worst_severity: str
    findings: list[FindingOut] = Field(default_factory=list)
    media: list[MediaOut] = Field(default_factory=list)


class UploadResult(BaseModel):
    uploaded: int
    source: str
    status: str
    inspection_id: str


class FindingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: FindingStatus
    resolution_notes: str | None = Field(default=None, max_length=1000)


class FleetStatsOut(BaseModel):
    active_trucks: int
    inspections_today: int
    inspections_pending: int
    inspections_complete_today: int
    open_findings: int


class AuthSessionOut(BaseModel):
    auth_mode: str
    user_id: str | None = None
    fleet_id: str | None = None
    role: str | None = None
