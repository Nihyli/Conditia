from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path


def test_legacy_sqlite_uuid_migration_preserves_relationships(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.db"
    fleet_id = "10000000-0000-0000-0000-000000000001"
    truck_id = "20000000-0000-0000-0000-000000000002"
    inspection_id = "30000000-0000-0000-0000-000000000003"
    media_id = "40000000-0000-0000-0000-000000000004"

    with closing(sqlite3.connect(database_path)) as connection:
        connection.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE fleets (id VARCHAR PRIMARY KEY);
            CREATE TABLE trucks (
                id VARCHAR PRIMARY KEY,
                fleet_id VARCHAR REFERENCES fleets(id)
            );
            CREATE TABLE inspections (
                id VARCHAR PRIMARY KEY,
                truck_id VARCHAR NOT NULL REFERENCES trucks(id)
            );
            CREATE TABLE inspection_media (
                id VARCHAR PRIMARY KEY,
                inspection_id VARCHAR NOT NULL REFERENCES inspections(id)
            );
            -- Present in any DB at revision 0002; later migrations alter it.
            CREATE TABLE analysis_jobs (
                id VARCHAR PRIMARY KEY,
                inspection_id VARCHAR NOT NULL REFERENCES inspections(id),
                status VARCHAR NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error VARCHAR,
                created_at DATETIME,
                updated_at DATETIME
            );
            """
        )
        connection.execute("INSERT INTO fleets(id) VALUES (?)", (fleet_id,))
        connection.execute(
            "INSERT INTO trucks(id, fleet_id) VALUES (?, ?)",
            (truck_id, fleet_id),
        )
        connection.execute(
            "INSERT INTO inspections(id, truck_id) VALUES (?, ?)",
            (inspection_id, truck_id),
        )
        connection.execute(
            "INSERT INTO inspection_media(id, inspection_id) VALUES (?, ?)",
            (media_id, inspection_id),
        )
        connection.commit()

    backend_dir = Path(__file__).parents[1]
    environment = {
        **os.environ,
        "DATABASE_URL": f"sqlite+aiosqlite:///{database_path.as_posix()}",
    }
    subprocess.run(  # noqa: S603 - fixed interpreter/module invocation
        [
            sys.executable,
            "-m",
            "alembic",
            "stamp",
            "0002_legacy_compatibility",
        ],
        cwd=backend_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(  # noqa: S603 - fixed interpreter/module invocation
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    with closing(sqlite3.connect(database_path)) as connection:
        inspection_row = connection.execute(
            "SELECT id, truck_id FROM inspections"
        ).fetchone()
        media_row = connection.execute(
            "SELECT id, inspection_id FROM inspection_media"
        ).fetchone()
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        version = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()

    assert inspection_row == (inspection_id.replace("-", ""), truck_id.replace("-", ""))
    assert media_row == (media_id.replace("-", ""), inspection_id.replace("-", ""))
    assert violations == []
    assert version == ("0008_security_hardening",)


def test_fresh_sqlite_upgrade_head_from_base(tmp_path: Path) -> None:
    """Upgrade from an empty database (no stamp) reaches head on SQLite.

    Reproduced CONFIG-001: ``op.drop_constraint`` outside batch mode crashes
    at migration 0008 when a prior migration created the constraint on SQLite.
    """
    database_path = tmp_path / "fresh.db"
    backend_dir = Path(__file__).parents[1]
    environment = {
        **os.environ,
        "DATABASE_URL": f"sqlite+aiosqlite:///{database_path.as_posix()}",
    }
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0

    with closing(sqlite3.connect(database_path)) as connection:
        version = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()
    assert version == ("0008_security_hardening",)
