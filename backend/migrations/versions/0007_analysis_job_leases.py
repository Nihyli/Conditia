"""Add lease columns to analysis_jobs so only expired work is reclaimed."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_analysis_job_leases"
down_revision: str | Sequence[str] | None = "0006_rls_policies"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "analysis_jobs", sa.Column("lease_owner", sa.String(), nullable=True)
    )
    op.add_column(
        "analysis_jobs",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("analysis_jobs", "lease_expires_at")
    op.drop_column("analysis_jobs", "lease_owner")
