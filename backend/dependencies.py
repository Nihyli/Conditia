"""Application composition root for replaceable infrastructure."""

from adapters.mobile import MobileAdapter
from adapters.registry import CaptureAdapterRegistry
from domain import IngestibleCaptureSource
from services.inspection_ingestion import InspectionIngestionService
from services.storage import storage_service

capture_adapters = CaptureAdapterRegistry(
    {
        IngestibleCaptureSource.MOBILE: MobileAdapter(storage_service),
    }
)
inspection_ingestion_service = InspectionIngestionService(
    adapters=capture_adapters,
    storage_cleanup=storage_service,
)


def get_inspection_ingestion_service() -> InspectionIngestionService:
    return inspection_ingestion_service
