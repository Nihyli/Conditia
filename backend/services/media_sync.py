"""Sync files on disk into inspection_media when DB rows are missing.

This handles uploads that wrote to storage/ but lost DB records (e.g. DB
recreated, or uvicorn started from a different working directory).
"""

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.db_models import InspectionMedia
from services.storage import storage_service

VIDEO_EXTS = {".mp4", ".mov", ".webm", ".avi", ".mkv"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _storage_roots() -> list[Path]:
    """Primary storage dir plus cwd/storage if files landed there by mistake."""
    roots = [storage_service.base.resolve()]
    alt = (Path.cwd() / "storage").resolve()
    if alt not in roots and alt.is_dir():
        roots.append(alt)
    # Parent project folder (running uvicorn from repo root)
    alt2 = (Path.cwd() / "backend" / "storage").resolve()
    if alt2 not in roots and alt2.is_dir():
        roots.append(alt2)
    return roots


def _iter_files_for_inspection(inspection_id: str) -> list[tuple[str, str, Path]]:
    """
    Yield (storage_path, capture_angle, absolute_file_path).
    Expected layout: {root}/{inspection_id}/{angle}/{filename}
    """
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


async def sync_inspection_media_from_disk(
    db: AsyncSession, inspection_id: str
) -> int:
    """Create inspection_media rows for on-disk files not yet in the DB. Returns count added."""
    existing = await db.execute(
        select(InspectionMedia.storage_path).where(
            InspectionMedia.inspection_id == inspection_id
        )
    )
    existing_paths = set(existing.scalars().all())

    added = 0
    for rel_path, angle, file_path in _iter_files_for_inspection(inspection_id):
        if rel_path in existing_paths:
            continue

        suffix = file_path.suffix.lower()
        if suffix in VIDEO_EXTS:
            media_type = "video"
        elif suffix in IMAGE_EXTS:
            media_type = "photo"
        else:
            continue

        # Ensure file exists under the canonical storage root (for /media serving).
        canonical = storage_service.base / inspection_id / angle / file_path.name
        if file_path.resolve() != canonical.resolve():
            canonical.parent.mkdir(parents=True, exist_ok=True)
            if not canonical.exists():
                canonical.write_bytes(file_path.read_bytes())

        db.add(
            InspectionMedia(
                inspection_id=inspection_id,
                media_type=media_type,
                capture_angle=angle,
                capture_source="mobile",
                storage_path=rel_path,
            )
        )
        added += 1

    if added:
        await db.commit()

    return added


async def get_inspection_media_rows(
    db: AsyncSession, inspection_id: str
) -> list[InspectionMedia]:
    """Return media rows, syncing from disk first when the DB is empty."""
    result = await db.execute(
        select(InspectionMedia)
        .where(InspectionMedia.inspection_id == inspection_id)
        .order_by(InspectionMedia.captured_at.asc())
    )
    rows = list(result.scalars().all())

    if not rows:
        await sync_inspection_media_from_disk(db, inspection_id)
        result = await db.execute(
            select(InspectionMedia)
            .where(InspectionMedia.inspection_id == inspection_id)
            .order_by(InspectionMedia.captured_at.asc())
        )
        rows = list(result.scalars().all())

    return rows
