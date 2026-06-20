"""Pydantic request/response models (API contract)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TruckCreate(BaseModel):
    vin: str
    make: str | None = None
    model: str | None = None
    year: int | None = None
    license_plate: str | None = None
    fleet_id: str | None = None


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
    truck_id: str
    capture_source: str = "mobile"
    created_by: str | None = None


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    inspection_id: str
    media_id: str | None
    title: str | None
    finding_type: str
    severity: str
    confidence: float
    zone: str | None
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
    capture_angle: str | None
    capture_source: str
    drone_flight_id: str | None
    storage_path: str
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
    status: str
    capture_source: str


class InspectionSummary(BaseModel):
    """Shape consumed by the dashboard's recent-inspections list + damage map."""

    id: str
    truck_id: str
    truck_label: str
    make: str | None
    model: str | None
    started_at: datetime
    status: str
    capture_source: str
    finding_count: int
    worst_severity: str
    findings: list[FindingOut] = Field(default_factory=list)
    media: list[MediaOut] = Field(default_factory=list)


class UploadResult(BaseModel):
    uploaded: int
    source: str
    status: str
    inspection_id: str


class FleetStatsOut(BaseModel):
    active_trucks: int
    inspections_today: int
    inspections_pending: int
    inspections_complete_today: int
    open_findings: int
