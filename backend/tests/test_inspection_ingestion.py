from io import BytesIO

import pytest
from fastapi import UploadFile

from adapters.base import CaptureMetadata, StoredMedia
from adapters.registry import CaptureAdapterRegistry
from database import SessionLocal
from domain import CaptureAngle, IngestibleCaptureSource
from models.db_models import Inspection, Truck
from services.inspection_ingestion import InspectionIngestionService


class SuccessfulAdapter:
    async def receive_media(self, inspection_id, files, capture_angle, metadata):
        del inspection_id, files, capture_angle, metadata
        return [
            StoredMedia(
                storage_path="inspection/front/media.png",
                media_type="photo",
                content_type="image/png",
                size_bytes=10,
            )
        ]

    def get_source_name(self) -> str:
        return "mobile"


class CleanupStorage:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    async def delete(self, path: str) -> None:
        self.deleted.append(path)


@pytest.mark.asyncio
async def test_ingestion_compensates_storage_when_database_commit_fails(
    monkeypatch,
) -> None:
    cleanup = CleanupStorage()
    service = InspectionIngestionService(
        adapters=CaptureAdapterRegistry(
            {IngestibleCaptureSource.MOBILE: SuccessfulAdapter()}
        ),
        storage_cleanup=cleanup,
    )
    async with SessionLocal() as db:
        truck = Truck(vin="1FUJGLDR0CSBT0041")
        db.add(truck)
        await db.flush()
        inspection = Inspection(truck_id=truck.id, status="uploading")
        db.add(inspection)
        await db.commit()

        async def fail_commit() -> None:
            raise RuntimeError("database unavailable")

        monkeypatch.setattr(db, "commit", fail_commit)
        file = UploadFile(filename="media.png", file=BytesIO(b"image"))

        with pytest.raises(RuntimeError, match="database unavailable"):
            await service.ingest(
                db,
                inspection=inspection,
                files=[file],
                angle=CaptureAngle.FRONT,
                source=IngestibleCaptureSource.MOBILE,
                metadata=CaptureMetadata(),
            )

    assert cleanup.deleted == ["inspection/front/media.png"]
