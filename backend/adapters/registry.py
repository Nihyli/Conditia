"""Application composition for capture-source implementations."""

from adapters.base import CaptureAdapter
from adapters.mobile import MobileAdapter
from domain import IngestibleCaptureSource

CAPTURE_ADAPTERS: dict[IngestibleCaptureSource, CaptureAdapter] = {
    IngestibleCaptureSource.MOBILE: MobileAdapter(),
}


def get_capture_adapter(source: IngestibleCaptureSource) -> CaptureAdapter:
    return CAPTURE_ADAPTERS[source]
