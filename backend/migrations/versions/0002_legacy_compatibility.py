"""Add durable jobs and finding lifecycle to pre-Alembic databases.

Existing prototype databases can be backed up, stamped at ``0001_initial``, and
then upgraded. Fresh databases already contain these objects, so the revision is
intentionally conditional.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_legacy_compatibility"
down_revision: str | Sequence[str] | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())

    if "analysis_jobs" not in tables:
        op.create_table(
            "analysis_jobs",
            sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("inspection_id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_error", sa.String(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
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

    finding_columns = {
        column["name"] for column in inspector.get_columns("findings")
    }
    with op.batch_alter_table("findings") as batch:
        if "status" not in finding_columns:
            batch.add_column(
                sa.Column(
                    "status",
                    sa.String(),
                    nullable=False,
                    server_default="open",
                )
            )
        if "resolved_at" not in finding_columns:
            batch.add_column(sa.Column("resolved_at", sa.DateTime(), nullable=True))
        if "resolution_notes" not in finding_columns:
            batch.add_column(sa.Column("resolution_notes", sa.String(), nullable=True))


def downgrade() -> None:
    # Downgrading would destroy lifecycle/audit data. Restore a backup instead.
    pass
