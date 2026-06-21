"""Create the initial Conditia application schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fleets",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "trucks",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("fleet_id", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("vin", sa.String(), nullable=False),
        sa.Column("make", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("license_plate", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("year IS NULL OR year >= 1900", name="ck_truck_year"),
        sa.ForeignKeyConstraint(["fleet_id"], ["fleets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vin"),
    )
    op.create_table(
        "inspections",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("truck_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("capture_source", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.CheckConstraint(
            "status IN ('uploading','submitted','processing','complete','review_required','failed')",
            name="ck_inspection_status",
        ),
        sa.CheckConstraint(
            "capture_source IN ('mobile','drone','fixed_camera','manual')",
            name="ck_inspection_capture_source",
        ),
        sa.ForeignKeyConstraint(["truck_id"], ["trucks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_inspections_truck_started",
        "inspections",
        ["truck_id", "started_at"],
    )
    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("inspection_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','running','complete','failed')",
            name="ck_analysis_job_status",
        ),
        sa.ForeignKeyConstraint(
            ["inspection_id"], ["inspections.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inspection_id", name="uq_analysis_job_inspection"),
    )
    op.create_index(
        "idx_analysis_jobs_status_created",
        "analysis_jobs",
        ["status", "created_at"],
    )
    op.create_table(
        "inspection_media",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("inspection_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("media_type", sa.String(), nullable=False),
        sa.Column("capture_angle", sa.String(), nullable=True),
        sa.Column("capture_source", sa.String(), nullable=False),
        sa.Column("drone_flight_id", sa.String(), nullable=True),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("gps_lat", sa.Float(), nullable=True),
        sa.Column("gps_lng", sa.Float(), nullable=True),
        sa.CheckConstraint("media_type IN ('photo','video')", name="ck_media_type"),
        sa.CheckConstraint(
            "capture_angle IN ('front','rear','driver_side','passenger_side','top','undercarriage')",
            name="ck_media_capture_angle",
        ),
        sa.CheckConstraint(
            "capture_source IN ('mobile','drone','fixed_camera','manual')",
            name="ck_media_capture_source",
        ),
        sa.CheckConstraint(
            "gps_lat IS NULL OR (gps_lat >= -90 AND gps_lat <= 90)",
            name="ck_media_gps_lat",
        ),
        sa.CheckConstraint(
            "gps_lng IS NULL OR (gps_lng >= -180 AND gps_lng <= 180)",
            name="ck_media_gps_lng",
        ),
        sa.ForeignKeyConstraint(
            ["inspection_id"], ["inspections.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_path", name="uq_media_storage_path"),
    )
    op.create_index(
        "idx_media_inspection_captured",
        "inspection_media",
        ["inspection_id", "captured_at"],
    )
    op.create_table(
        "findings",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("inspection_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("media_id", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("finding_type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolution_notes", sa.String(), nullable=True),
        sa.Column("zone", sa.String(), nullable=True),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("bounding_box", sa.JSON(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("annotated_image_path", sa.String(), nullable=True),
        sa.Column("first_seen_inspection_id", sa.Uuid(as_uuid=False), nullable=True),
        sa.CheckConstraint(
            "finding_type IN ('dent','scratch','crack','missing_component','rust','anomaly')",
            name="ck_finding_type",
        ),
        sa.CheckConstraint(
            "severity IN ('low','medium','high','critical','clear')",
            name="ck_finding_severity",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_finding_confidence",
        ),
        sa.CheckConstraint(
            "status IN ('open','acknowledged','resolved','false_positive')",
            name="ck_finding_status",
        ),
        sa.ForeignKeyConstraint(
            ["first_seen_inspection_id"],
            ["inspections.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["inspection_id"], ["inspections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["media_id"], ["inspection_media.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_findings_inspection", "findings", ["inspection_id"])
    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("inspection_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("summary", sa.String(), nullable=True),
        sa.Column("total_findings", sa.Integer(), nullable=False),
        sa.Column("critical_findings", sa.Integer(), nullable=False),
        sa.Column("pdf_path", sa.String(), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["inspection_id"], ["inspections.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inspection_id", name="uq_report_inspection"),
    )


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_index("idx_findings_inspection", table_name="findings")
    op.drop_table("findings")
    op.drop_index("idx_media_inspection_captured", table_name="inspection_media")
    op.drop_table("inspection_media")
    op.drop_index("idx_analysis_jobs_status_created", table_name="analysis_jobs")
    op.drop_table("analysis_jobs")
    op.drop_index("idx_inspections_truck_started", table_name="inspections")
    op.drop_table("inspections")
    op.drop_table("trucks")
    op.drop_table("fleets")
