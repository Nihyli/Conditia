"""Store timestamps as timezone-aware (TIMESTAMPTZ) on PostgreSQL.

The ORM produces timezone-aware UTC values (``datetime.now(timezone.utc)``), but
the initial schema created naive ``TIMESTAMP`` columns. asyncpg refuses to write
an aware datetime into a naive column, so widen every timestamp to
``TIMESTAMPTZ``. SQLite has no timezone-aware column type and needs no rewrite.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_timestamptz"
down_revision: str | Sequence[str] | None = "0003_normalize_sqlite_uuids"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# (table, column, nullable)
_COLUMNS: tuple[tuple[str, str, bool], ...] = (
    ("fleets", "created_at", False),
    ("trucks", "created_at", False),
    ("inspections", "started_at", False),
    ("inspections", "completed_at", True),
    ("inspection_media", "captured_at", False),
    ("analysis_jobs", "created_at", False),
    ("analysis_jobs", "updated_at", False),
    ("findings", "resolved_at", True),
    ("reports", "generated_at", False),
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for table, column, nullable in _COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(),
            existing_nullable=nullable,
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for table, column, nullable in _COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.DateTime(),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=nullable,
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )
