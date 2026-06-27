"""SQLAlchemy ORM models.

`capture_source` records what collected the footage. Only mobile ingestion is
registered by the current application; other allowed values support imported
or historical records. `first_seen_inspection_id` powers change detection.

UUIDs are stored as strings so the same models run on SQLite (local dev) and
Postgres/Supabase (production) without modification.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base

# Timezone-aware timestamps (TIMESTAMPTZ on Postgres) to match the tz-aware UTC
# values from `_now()`. asyncpg rejects writing aware datetimes into a naive
# TIMESTAMP column; SQLite ignores the flag.
TZDateTime = DateTime(timezone=True)


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Fleet(Base):
    __tablename__ = "fleets"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=_now)


class Truck(Base):
    __tablename__ = "trucks"
    __table_args__ = (CheckConstraint("year IS NULL OR year >= 1900", name="ck_truck_year"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    fleet_id: Mapped[str | None] = mapped_column(
        ForeignKey("fleets.id", ondelete="RESTRICT")
    )
    vin: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    make: Mapped[str | None] = mapped_column(String)
    model: Mapped[str | None] = mapped_column(String)
    year: Mapped[int | None] = mapped_column(Integer)
    license_plate: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=_now)


class Inspection(Base):
    __tablename__ = "inspections"
    __table_args__ = (
        CheckConstraint(
            "status IN ('uploading','submitted','processing','complete','review_required','failed')",
            name="ck_inspection_status",
        ),
        CheckConstraint(
            "capture_source IN ('mobile','drone','fixed_camera','manual')",
            name="ck_inspection_capture_source",
        ),
        Index("idx_inspections_truck_started", "truck_id", "started_at"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    truck_id: Mapped[str] = mapped_column(
        ForeignKey("trucks.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(TZDateTime, default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, default="uploading")
    # mobile | drone | fixed_camera | manual
    capture_source: Mapped[str] = mapped_column(String, default="mobile")
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)


class InspectionMedia(Base):
    __tablename__ = "inspection_media"
    __table_args__ = (
        CheckConstraint("media_type IN ('photo','video')", name="ck_media_type"),
        CheckConstraint(
            "capture_angle IN ('front','rear','driver_side','passenger_side','top','undercarriage')",
            name="ck_media_capture_angle",
        ),
        CheckConstraint(
            "capture_source IN ('mobile','drone','fixed_camera','manual')",
            name="ck_media_capture_source",
        ),
        CheckConstraint(
            "gps_lat IS NULL OR (gps_lat >= -90 AND gps_lat <= 90)",
            name="ck_media_gps_lat",
        ),
        CheckConstraint(
            "gps_lng IS NULL OR (gps_lng >= -180 AND gps_lng <= 180)",
            name="ck_media_gps_lng",
        ),
        UniqueConstraint("storage_path", name="uq_media_storage_path"),
        Index("idx_media_inspection_captured", "inspection_id", "captured_at"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    inspection_id: Mapped[str] = mapped_column(
        ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False
    )
    media_type: Mapped[str] = mapped_column(String)  # photo | video
    capture_angle: Mapped[str | None] = mapped_column(String)
    capture_source: Mapped[str] = mapped_column(String, default="mobile")
    drone_flight_id: Mapped[str | None] = mapped_column(String, nullable=True)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(TZDateTime, default=_now)
    gps_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_lng: Mapped[float | None] = mapped_column(Float, nullable=True)


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','running','complete','failed')",
            name="ck_analysis_job_status",
        ),
        UniqueConstraint("inspection_id", name="uq_analysis_job_inspection"),
        Index("idx_analysis_jobs_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    inspection_id: Mapped[str] = mapped_column(
        ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime, default=_now, onupdate=_now
    )


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        CheckConstraint(
            "finding_type IN ('dent','scratch','crack','missing_component','rust','anomaly')",
            name="ck_finding_type",
        ),
        CheckConstraint(
            "severity IN ('low','medium','high','critical','clear')",
            name="ck_finding_severity",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_finding_confidence"
        ),
        CheckConstraint(
            "status IN ('open','acknowledged','resolved','false_positive')",
            name="ck_finding_status",
        ),
        Index("idx_findings_inspection", "inspection_id"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    inspection_id: Mapped[str] = mapped_column(
        ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False
    )
    media_id: Mapped[str | None] = mapped_column(
        ForeignKey("inspection_media.id", ondelete="SET NULL")
    )
    title: Mapped[str | None] = mapped_column(String)
    # dent | scratch | crack | missing_component | rust | anomaly
    finding_type: Mapped[str] = mapped_column(String)
    # critical | medium | low | clear  (also accepts 'high' -> mapped to critical)
    severity: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String, default="open")
    resolved_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(String, nullable=True)
    # truck silhouette zone used by the dashboard damage map
    zone: Mapped[str | None] = mapped_column(String)
    location: Mapped[str | None] = mapped_column(String)
    bounding_box: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str | None] = mapped_column(String)
    annotated_image_path: Mapped[str | None] = mapped_column(String)
    first_seen_inspection_id: Mapped[str | None] = mapped_column(
        ForeignKey("inspections.id", ondelete="SET NULL"), nullable=True
    )


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("inspection_id", name="uq_report_inspection"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=_uuid)
    inspection_id: Mapped[str] = mapped_column(
        ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False
    )
    generated_at: Mapped[datetime] = mapped_column(TZDateTime, default=_now)
    summary: Mapped[str | None] = mapped_column(String)
    total_findings: Mapped[int] = mapped_column(Integer, default=0)
    critical_findings: Mapped[int] = mapped_column(Integer, default=0)
    pdf_path: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
