"""SQLAlchemy ORM models.

Hardware-agnostic by design: `capture_source` is the only place the system
records what collected the footage. `drone_flight_id` is NULL for mobile
captures and populated automatically for drone captures in Phase 5 with no
schema change. `first_seen_inspection_id` powers change detection.

UUIDs are stored as strings so the same models run on SQLite (local dev) and
Postgres/Supabase (production) without modification.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database import Base

# Portable column types so the same models run on SQLite (dev) and Postgres
# (Supabase). Timestamps are timezone-aware (TIMESTAMPTZ on Postgres) to match
# the tz-aware values produced by `_now()`; JSON becomes JSONB on Postgres.
TZDateTime = DateTime(timezone=True)
PortableJSON = JSON().with_variant(JSONB, "postgresql")


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Fleet(Base):
    __tablename__ = "fleets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=_now)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    full_name: Mapped[str | None] = mapped_column(String)
    # admin | fleet_manager | inspector | viewer
    role: Mapped[str] = mapped_column(String, default="viewer")
    fleet_id: Mapped[str | None] = mapped_column(ForeignKey("fleets.id"))
    # local | supabase
    auth_provider: Mapped[str] = mapped_column(String, default="local")
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=_now)


class Truck(Base):
    __tablename__ = "trucks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    fleet_id: Mapped[str | None] = mapped_column(ForeignKey("fleets.id"))
    vin: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    make: Mapped[str | None] = mapped_column(String)
    model: Mapped[str | None] = mapped_column(String)
    year: Mapped[int | None] = mapped_column(Integer)
    license_plate: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=_now)


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    truck_id: Mapped[str] = mapped_column(ForeignKey("trucks.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(TZDateTime, default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
    # pending | processing | complete | failed
    status: Mapped[str] = mapped_column(String, default="pending")
    # mobile | drone | fixed_camera | manual
    capture_source: Mapped[str] = mapped_column(String, default="mobile")
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)


class InspectionMedia(Base):
    __tablename__ = "inspection_media"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    inspection_id: Mapped[str] = mapped_column(
        ForeignKey("inspections.id"), nullable=False
    )
    media_type: Mapped[str] = mapped_column(String)  # photo | video
    capture_angle: Mapped[str | None] = mapped_column(String)
    capture_source: Mapped[str] = mapped_column(String, default="mobile")
    drone_flight_id: Mapped[str | None] = mapped_column(String, nullable=True)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(TZDateTime, default=_now)
    gps_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_lng: Mapped[float | None] = mapped_column(Float, nullable=True)


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    inspection_id: Mapped[str] = mapped_column(
        ForeignKey("inspections.id"), nullable=False
    )
    media_id: Mapped[str | None] = mapped_column(ForeignKey("inspection_media.id"))
    title: Mapped[str | None] = mapped_column(String)
    # dent | scratch | crack | missing_component | rust | anomaly
    finding_type: Mapped[str] = mapped_column(String)
    # critical | medium | low | clear  (also accepts 'high' -> mapped to critical)
    severity: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    # truck silhouette zone used by the dashboard damage map
    zone: Mapped[str | None] = mapped_column(String)
    location: Mapped[str | None] = mapped_column(String)
    bounding_box: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)
    description: Mapped[str | None] = mapped_column(String)
    annotated_image_path: Mapped[str | None] = mapped_column(String)
    first_seen_inspection_id: Mapped[str | None] = mapped_column(
        ForeignKey("inspections.id"), nullable=True
    )


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    inspection_id: Mapped[str] = mapped_column(
        ForeignKey("inspections.id"), nullable=False
    )
    generated_at: Mapped[datetime] = mapped_column(TZDateTime, default=_now)
    summary: Mapped[str | None] = mapped_column(String)
    total_findings: Mapped[int] = mapped_column(Integer, default=0)
    critical_findings: Mapped[int] = mapped_column(Integer, default=0)
    pdf_path: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(PortableJSON, nullable=True)
