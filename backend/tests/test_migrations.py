from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_legacy_sqlite_uuid_migration_preserves_relationships(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.db"
    fleet_id = "10000000-0000-0000-0000-000000000001"
    truck_id = "20000000-0000-0000-0000-000000000002"
    inspection_id = "30000000-0000-0000-0000-000000000003"
    media_id = "40000000-0000-0000-0000-000000000004"

    with sqlite3.connect(database_path) as connection:
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

    with sqlite3.connect(database_path) as connection:
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
    assert version == ("0003_normalize_legacy_sqlite_uuids",)
