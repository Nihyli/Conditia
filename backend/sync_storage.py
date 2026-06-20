"""Register files in storage/ into inspection_media (stdlib only — no venv required).

Run from the backend folder:
    python sync_storage.py

Or with the project venv:
    .\.venv\Scripts\Activate.ps1
    python sync_storage.py
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent
CANONICAL_STORAGE = BACKEND_ROOT / "storage"

VIDEO_EXTS = {".mp4", ".mov", ".webm", ".avi", ".mkv"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _db_candidates() -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for p in (
        BACKEND_ROOT / "conditia.db",
        Path.cwd() / "conditia.db",
        Path.cwd() / "backend" / "conditia.db",
    ):
        resolved = p.resolve()
        if resolved.exists() and resolved not in seen:
            seen.add(resolved)
            out.append(resolved)
    return out


def _storage_roots() -> list[Path]:
    roots: list[Path] = []
    seen: set[Path] = set()
    for p in (
        CANONICAL_STORAGE,
        Path.cwd() / "storage",
        Path.cwd() / "backend" / "storage",
        BACKEND_ROOT.parent / "storage",
    ):
        resolved = p.resolve()
        if resolved.is_dir() and resolved not in seen:
            seen.add(resolved)
            roots.append(resolved)
    return roots


def _iter_disk_files(inspection_id: str) -> list[tuple[str, str, Path]]:
    found: list[tuple[str, str, Path]] = []
    seen_paths: set[str] = set()

    for root in _storage_roots():
        insp_dir = root / inspection_id
        if not insp_dir.is_dir():
            continue
        for angle_dir in insp_dir.iterdir():
            if not angle_dir.is_dir():
                continue
            angle = angle_dir.name
            for file_path in angle_dir.iterdir():
                if not file_path.is_file():
                    continue
                rel = f"{inspection_id}/{angle}/{file_path.name}".replace("\\", "/")
                if rel in seen_paths:
                    continue
                seen_paths.add(rel)
                found.append((rel, angle, file_path))
    return found


def _media_type(path: Path) -> str | None:
    ext = path.suffix.lower()
    if ext in VIDEO_EXTS:
        return "video"
    if ext in IMAGE_EXTS:
        return "photo"
    return None


def sync_inspection(conn: sqlite3.Connection, inspection_id: str) -> int:
    existing = {
        row[0]
        for row in conn.execute(
            "SELECT storage_path FROM inspection_media WHERE inspection_id = ?",
            (inspection_id,),
        )
    }

    added = 0
    now = datetime.now(timezone.utc).isoformat()

    for rel_path, angle, file_path in _iter_disk_files(inspection_id):
        if rel_path in existing:
            continue
        mtype = _media_type(file_path)
        if mtype is None:
            continue

        canonical = CANONICAL_STORAGE / inspection_id / angle / file_path.name
        if file_path.resolve() != canonical.resolve():
            canonical.parent.mkdir(parents=True, exist_ok=True)
            if not canonical.exists():
                canonical.write_bytes(file_path.read_bytes())

        conn.execute(
            """
            INSERT INTO inspection_media
              (id, inspection_id, media_type, capture_angle, capture_source,
               storage_path, captured_at)
            VALUES (?, ?, ?, ?, 'mobile', ?, ?)
            """,
            (str(uuid.uuid4()), inspection_id, mtype, angle, rel_path, now),
        )
        added += 1

    return added


def main() -> None:
    dbs = _db_candidates()
    if not dbs:
        print("No conditia.db found. Start the backend once to create it.")
        return

    print(f"Canonical storage: {CANONICAL_STORAGE.resolve()}")
    print("Scanning storage roots:", [str(p) for p in _storage_roots()])

    for db_path in dbs:
        print(f"\nDatabase: {db_path}")
        conn = sqlite3.connect(db_path)

        try:
            rows = conn.execute("SELECT id FROM inspections").fetchall()
        except sqlite3.OperationalError as e:
            print(f"  Skipping ({e})")
            conn.close()
            continue

        print(f"  {len(rows)} inspection(s)")
        total = 0
        for (insp_id,) in rows:
            n = sync_inspection(conn, insp_id)
            if n:
                print(f"  {insp_id}: synced {n} file(s)")
                total += n
            else:
                print(f"  {insp_id}: no new files on disk")

        conn.commit()
        conn.close()
        print(f"  Done — {total} media row(s) added.")


if __name__ == "__main__":
    main()
