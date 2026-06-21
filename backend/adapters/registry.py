"""Extensible lookup for configured capture-source implementations."""

from adapters.base import CaptureAdapter
from domain import IngestibleCaptureSource


class CaptureAdapterRegistry:
    def __init__(
        self,
        adapters: dict[IngestibleCaptureSource, CaptureAdapter],
    ) -> None:
        self._adapters = dict(adapters)

    def get(self, source: IngestibleCaptureSource) -> CaptureAdapter:
        return self._adapters[source]
