"""Idempotent inspection-analysis workflow claimed after explicit finalization."""

import logging
import tempfile
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import anyio
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import SessionLocal
from domain import InspectionStatus
from models.db_models import Finding, Inspection, InspectionMedia, Report
from services import report_generator
from services.change_detection import find_first_occurrence
from services.storage import storage_service
from services.vision import (
    DetectionBatch,
    DetectionFailed,
    DetectorUnavailable,
    detect_damage,
)

logger = logging.getLogger(__name__)
VIDEO_SUFFIXES = (".mp4", ".mov", ".webm", ".avi")


class FrameExtractionUnavailable(Exception):
    pass


class MaterializedStorage(Protocol):
    def materialize(self, path: str) -> AbstractAsyncContextManager[Path]: ...


class ReportBuilder(Protocol):
    async def __call__(
        self,
        db: AsyncSession,
        inspection_id: str,
        *,
        requires_human_review: bool = False,
    ) -> Report: ...


Detector = Callable[[Path], Awaitable[DetectionBatch]]


@dataclass(frozen=True)
class AnalysisDependencies:
    storage: MaterializedStorage
    detector: Detector
    report_builder: ReportBuilder


def default_analysis_dependencies() -> AnalysisDependencies:
    return AnalysisDependencies(
        storage=storage_service,
        detector=detect_damage,
        report_builder=report_generator.generate,
    )


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


async def _detect_all(
    media_inputs: list[tuple[str, str]],
    storage: MaterializedStorage,
    detector: Detector,
) -> tuple[list[tuple[str, list]], bool]:
    """Run detection (storage I/O, frame extraction, model calls) with no open DB
    transaction, returning (media_id, detections) pairs to persist afterward."""
    results: list[tuple[str, list]] = []
    requires_review = False
    for media_id, storage_path in media_inputs:
        detections: list = []
        async with storage.materialize(storage_path) as local_path:
            with tempfile.TemporaryDirectory(prefix="conditia-frames-") as frame_dir:
                frames = await anyio.to_thread.run_sync(
                    extract_frames, local_path, Path(frame_dir)
                )
                for frame_path in frames:
                    batch = await detector(frame_path)
                    requires_review = requires_review or batch.requires_human_review
                    detections.extend(batch.detections)
        results.append((media_id, detections))
    return results, requires_review


async def analyze_inspection(
    inspection_id: str,
    dependencies: AnalysisDependencies | None = None,
) -> None:
    """Claim one submitted inspection and analyze it exactly once per submission.

    Detection runs between two short transactions instead of inside one long one:
    a claim txn flips the status and snapshots immutable inputs, detection happens
    with no transaction held, then a write txn atomically replaces findings,
    report, and status.
    """
    dependencies = dependencies or default_analysis_dependencies()

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
        truck_id = inspection.truck_id
        media_result = await db.execute(
            select(InspectionMedia.id, InspectionMedia.storage_path).where(
                InspectionMedia.inspection_id == inspection_id
            )
        )
        media_inputs = [(row.id, row.storage_path) for row in media_result.all()]

    try:
        if not media_inputs:
            raise FrameExtractionUnavailable("Inspection has no media")

        detected, requires_review = await _detect_all(
            media_inputs, dependencies.storage, dependencies.detector
        )

        async with SessionLocal() as db:
            await db.execute(
                delete(Finding).where(Finding.inspection_id == inspection_id)
            )
            for media_id, detections in detected:
                for detection in detections:
                    first_seen = await find_first_occurrence(
                        db=db,
                        truck_id=truck_id,
                        finding_type=detection.finding_type,
                        zone=detection.zone,
                        current_inspection_id=inspection_id,
                    )
                    db.add(
                        Finding(
                            inspection_id=inspection_id,
                            media_id=media_id,
                            title=detection.description
                            or detection.finding_type.title(),
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
            await db.flush()
            await dependencies.report_builder(
                db,
                inspection_id,
                requires_human_review=requires_review,
            )
            inspection = await db.get(Inspection, inspection_id)
            if inspection is not None:
                inspection.completed_at = datetime.now(timezone.utc)
                inspection.status = (
                    InspectionStatus.REVIEW_REQUIRED.value
                    if requires_review
                    else InspectionStatus.COMPLETE.value
                )
            await db.commit()
    except (DetectorUnavailable, DetectionFailed, FrameExtractionUnavailable):
        logger.warning(
            "Inspection analysis requires review",
            extra={"inspection_id": inspection_id},
        )
        await _set_terminal_status(inspection_id, InspectionStatus.REVIEW_REQUIRED)
    except Exception:
        logger.exception(
            "Inspection analysis failed",
            extra={"inspection_id": inspection_id},
        )
        await _set_terminal_status(inspection_id, InspectionStatus.FAILED)
