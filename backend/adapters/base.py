from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol

from fastapi import UploadFile


@dataclass(frozen=True)
class CaptureMetadata:
    gps_lat: float | None = None
    gps_lng: float | None = None
    drone_flight_id: str | None = None


@dataclass(frozen=True)
class StoredMedia:
    storage_path: str
    media_type: str
    content_type: str
    size_bytes: int


class StoredUpload(Protocol):
    """Small storage result contract required by capture adapters."""

    storage_path: str
    media_type: str
    content_type: str
    size_bytes: int


class MediaWriter(Protocol):
    """Write/delete capability required during capture ingestion."""

    async def upload(
        self,
        file: UploadFile,
        inspection_id: str,
        capture_angle: str,
    ) -> StoredUpload: ...

    async def delete(self, path: str) -> None: ...


class CaptureAdapter(ABC):
    """Source-specific media ingestion contract."""

    @abstractmethod
    async def receive_media(
        self,
        inspection_id: str,
        files: list[UploadFile],
        capture_angle: str,
        metadata: CaptureMetadata,
    ) -> list[StoredMedia]:
        """Accept raw media, store it, return storage paths.

        Return application-owned storage keys and verified media metadata.
        """
        raise NotImplementedError

    @abstractmethod
    def get_source_name(self) -> str:
        """Return the persisted capture-source value."""
        raise NotImplementedError
