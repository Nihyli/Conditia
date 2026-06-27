"""Normalize UUID text in legacy SQLite databases.

SQLAlchemy's portable ``Uuid(as_uuid=False)`` stores SQLite UUIDs as 32
hexadecimal characters. Prototype databases stored canonical 36-character
UUID strings instead. Mixed representations make otherwise valid foreign-key
lookups return no rows, so normalize both primary and foreign keys together.
PostgreSQL uses its native UUID type and needs no data rewrite.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_normalize_sqlite_uuids"
down_revision: str | Sequence[str] | None = "0002_legacy_compatibility"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UUID_COLUMNS: tuple[tuple[str, str], ...] = (
    ("fleets", "id"),
    ("trucks", "id"),
    ("trucks", "fleet_id"),
    ("inspections", "id"),
    ("inspections", "truck_id"),
    ("inspection_media", "id"),
    ("inspection_media", "inspection_id"),
    ("analysis_jobs", "id"),
    ("analysis_jobs", "inspection_id"),
    ("findings", "id"),
    ("findings", "inspection_id"),
    ("findings", "media_id"),
    ("findings", "first_seen_inspection_id"),
    ("reports", "id"),
    ("reports", "inspection_id"),
)


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name != "sqlite":
        return

    tables = set(connection.dialect.get_table_names(connection))
    connection.exec_driver_sql("PRAGMA defer_foreign_keys=ON")
    for table, column in UUID_COLUMNS:
        if table not in tables:
            continue
        columns = {
            item["name"]
            for item in connection.dialect.get_columns(connection, table)
        }
        if column not in columns:
            continue
        connection.exec_driver_sql(
            f'UPDATE "{table}" '
            f'SET "{column}" = replace("{column}", \'-\', \'\') '
            f'WHERE length("{column}") = 36'  # noqa: S608 - fixed identifiers
        )

    violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(
            "Legacy UUID normalization would violate foreign keys: "
            f"{violations[:5]}"
        )


def downgrade() -> None:
    # Both representations decode to the same UUID. Restoring formatting adds
    # no semantic value and would require another coordinated FK rewrite.
    pass
