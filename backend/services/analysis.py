"""Idempotent inspection-analysis workflow claimed after explicit finalization."""

import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import anyio
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import SessionLocal
from domain import InspectionStatus
from models.db_models import Finding, Inspection, InspectionMedia
from services import report_generator
from services.change_detection import find_first_occurrence
from services.storage import storage_service
from services.vision import DetectionFailed, DetectorUnavailable, detect_damage

logger = logging.getLogger(__name__)
VIDEO_SUFFIXES = (".mp4", ".mov", ".webm", ".avi")


class FrameExtractionUnavailable(Exception):
    pass


def extract_frames(
    media_path: Path,
    output_directory: Path,
    interval_seconds: int = 2,
) -> list[Path]:
    if media_path.suffix.lower() not in VIDEO_SUFFIXES:
        return [media_path]
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise FrameExtractionUnavailable("Video analysis is not configured") from exc

    capture = cv2.VideoCapture(str(media_path))
    if not capture.isOpened():
        capture.release()
        raise FrameExtractionUnavailable("Video could not be decoded")

    try:
        fps = capture.get(cv2.CAP_PROP_FPS) or 30
        step = max(1, int(fps * interval_seconds))
        frames: list[Path] = []
        index = 0
        saved = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if index % step == 0:
                frame_path = output_directory / f"frame_{saved}.jpg"
                if not cv2.imwrite(str(frame_path), frame):
                    raise FrameExtractionUnavailable("Video frame could not be stored")
                frames.append(frame_path)
                saved += 1
            index += 1
        if not frames:
            raise FrameExtractionUnavailable("Video contains no decodable frames")
        return frames
    finally:
        capture.release()


async def _set_terminal_status(inspection_id: str, status: InspectionStatus) -> None:
    async with SessionLocal() as db:
        inspection = await db.get(Inspection, inspection_id)
        if inspection is None:
            return
        inspection.status = status.value
        inspection.completed_at = datetime.now(timezone.utc)
        await db.commit()


async def _analyze_frames(
    db: AsyncSession,
    inspection: Inspection,
    media: InspectionMedia,
    frames: list[Path],
) -> bool:
    requires_review = False
    for frame_path in frames:
        batch = await detect_damage(frame_path)
        requires_review = requires_review or batch.requires_human_review
        for detection in batch.detections:
            first_seen = await find_first_occurrence(
                db=db,
                truck_id=inspection.truck_id,
                finding_type=detection.finding_type,
                zone=detection.zone,
                current_inspection_id=inspection.id,
            )
            db.add(
                Finding(
                    inspection_id=inspection.id,
                    media_id=media.id,
                    title=detection.description or detection.finding_type.title(),
                    finding_type=detection.finding_type,
                    severity=detection.severity,
                    confidence=detection.confidence,
                    zone=detection.zone,
                    location=detection.location,
                    bounding_box=detection.bounding_box,
                    description=detection.description,
                    first_seen_inspection_id=first_seen,
                )
            )
    return requires_review


async def analyze_inspection(inspection_id: str) -> None:
    """Claim one submitted inspection and analyze it exactly once per submission."""
    async with SessionLocal() as db:
        claim = await db.execute(
            update(Inspection)
            .where(
                Inspection.id == inspection_id,
                Inspection.status == InspectionStatus.SUBMITTED.value,
            )
            .values(status=InspectionStatus.PROCESSING.value)
        )
        await db.commit()
        if claim.rowcount != 1:
            return

        inspection = await db.get(Inspection, inspection_id)
        if inspection is None:
            return

        try:
            media_result = await db.execute(
                select(InspectionMedia).where(
                    InspectionMedia.inspection_id == inspection_id
                )
            )
            media_items = list(media_result.scalars().all())
            if not media_items:
                raise FrameExtractionUnavailable("Inspection has no media")

            await db.execute(delete(Finding).where(Finding.inspection_id == inspection_id))
            requires_review = False

            for media in media_items:
                async with storage_service.materialize(media.storage_path) as local_path:
                    with tempfile.TemporaryDirectory(
                        prefix="conditia-frames-"
                    ) as frame_directory:
                        frames = await anyio.to_thread.run_sync(
                            extract_frames,
                            local_path,
                            Path(frame_directory),
                        )
                        requires_review = (
                            await _analyze_frames(db, inspection, media, frames)
                            or requires_review
                        )

            await db.flush()
            await report_generator.generate(
                db,
                inspection_id,
                requires_human_review=requires_review,
            )
            inspection.completed_at = datetime.now(timezone.utc)
            inspection.status = (
                InspectionStatus.REVIEW_REQUIRED.value
                if requires_review
                else InspectionStatus.COMPLETE.value
            )
            await db.commit()
        except (DetectorUnavailable, DetectionFailed, FrameExtractionUnavailable):
            await db.rollback()
            logger.warning(
                "Inspection analysis requires review",
                extra={"inspection_id": inspection_id},
            )
            await _set_terminal_status(
                inspection_id, InspectionStatus.REVIEW_REQUIRED
            )
        except Exception:
            await db.rollback()
            logger.exception(
                "Inspection analysis failed",
                extra={"inspection_id": inspection_id},
            )
            await _set_terminal_status(inspection_id, InspectionStatus.FAILED)
