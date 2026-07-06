"""Application service for the inspection write lifecycle."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from fastapi import UploadFile
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.base import CaptureMetadata, StoredMedia
from adapters.registry import CaptureAdapterRegistry
from config import settings
from domain import (
    AnalysisJobStatus,
    CaptureAngle,
    IngestibleCaptureSource,
    InspectionStatus,
)
from models.db_models import AnalysisJob, Inspection, InspectionMedia
from services.coverage import missing_required_angles

logger = logging.getLogger(__name__)


class MediaCleanup(Protocol):
    async def delete(self, path: str) -> None: ...


class InspectionConflict(Exception):
    """The requested write is not valid for the inspection's current state."""


@dataclass(frozen=True)
class IngestionResult:
    uploaded: int
    source: str


@dataclass(frozen=True)
class FinalizationResult:
    inspection: Inspection
    job_id: str


class InspectionIngestionService:
    """Own state changes, persistence, and storage compensation for ingestion."""

    def __init__(
        self,
        adapters: CaptureAdapterRegistry,
        storage_cleanup: MediaCleanup,
    ) -> None:
        self._adapters = adapters
        self._storage_cleanup = storage_cleanup

    async def start(
        self,
        db: AsyncSession,
        *,
        truck_id: str,
        source: IngestibleCaptureSource,
        created_by: str | None = None,
    ) -> Inspection:
        inspection = Inspection(
            truck_id=truck_id,
            capture_source=source.value,
            status=InspectionStatus.UPLOADING.value,
            created_by=created_by,
        )
        db.add(inspection)
        await db.commit()
        await db.refresh(inspection)
        return inspection

    async def ingest(
        self,
        db: AsyncSession,
        *,
        inspection: Inspection,
        files: list[UploadFile],
        angle: CaptureAngle,
        source: IngestibleCaptureSource,
        metadata: CaptureMetadata,
    ) -> IngestionResult:
        if inspection.status != InspectionStatus.UPLOADING.value:
            raise InspectionConflict("Inspection is not accepting uploads")

        media_count = await db.scalar(
            select(func.count())
            .select_from(InspectionMedia)
            .where(InspectionMedia.inspection_id == inspection.id)
        )
        if (media_count or 0) + len(files) > settings.max_media_per_inspection:
            raise InspectionConflict(
                f"At most {settings.max_media_per_inspection} media files are allowed per inspection"
            )

        adapter = self._adapters.get(source)
        stored_items = await adapter.receive_media(
            inspection.id,
            files,
            angle.value,
            metadata,
        )
        try:
            for item in stored_items:
                db.add(
                    InspectionMedia(
                        inspection_id=inspection.id,
                        media_type=item.media_type,
                        capture_angle=angle.value,
                        capture_source=adapter.get_source_name(),
                        storage_path=item.storage_path,
                        gps_lat=metadata.gps_lat,
                        gps_lng=metadata.gps_lng,
                    )
                )
            inspection.capture_source = adapter.get_source_name()
            await db.commit()
        except Exception:
            await db.rollback()
            await self._delete_after_failed_commit(stored_items)
            raise

        return IngestionResult(
            uploaded=len(stored_items),
            source=adapter.get_source_name(),
        )

    async def finalize(
        self,
        db: AsyncSession,
        *,
        inspection: Inspection,
    ) -> FinalizationResult:
        if inspection.status != InspectionStatus.UPLOADING.value:
            raise InspectionConflict("Inspection has already been finalized")

        media_count = await db.scalar(
            select(func.count())
            .select_from(InspectionMedia)
            .where(InspectionMedia.inspection_id == inspection.id)
        )
        if not media_count:
            raise InspectionConflict(
                "Upload at least one media file before finalizing"
            )

        missing = await missing_required_angles(db, inspection.id)
        if missing:
            raise InspectionConflict(
                "Missing required capture angles: "
                + ", ".join(missing)
            )

        transition = await db.execute(
            update(Inspection)
            .where(
                Inspection.id == inspection.id,
                Inspection.status == InspectionStatus.UPLOADING.value,
            )
            .values(status=InspectionStatus.SUBMITTED.value)
        )
        if transition.rowcount != 1:
            await db.rollback()
            raise InspectionConflict("Inspection has already been finalized")

        job = AnalysisJob(
            inspection_id=inspection.id,
            status=AnalysisJobStatus.PENDING.value,
        )
        db.add(job)
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise InspectionConflict("Inspection has already been finalized") from exc

        await db.refresh(inspection)
        return FinalizationResult(inspection=inspection, job_id=job.id)

    async def _delete_after_failed_commit(
        self,
        stored_items: list[StoredMedia],
    ) -> None:
        for item in stored_items:
            try:
                await self._storage_cleanup.delete(item.storage_path)
            except Exception:
                logger.exception(
                    "Could not clean up media after database failure",
                    extra={"storage_path": item.storage_path},
                )
