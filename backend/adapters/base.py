from abc import ABC, abstractmethod
from dataclasses import dataclass

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


class CaptureAdapter(ABC):
    """Abstract interface for all capture sources.

    Mobile, drone, and fixed camera all implement this. Adding a new capture
    source means implementing this class only -- no other file in the system
    changes. This is the entire point of the hardware-agnostic architecture.
    """

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
        """Return 'mobile', 'drone', 'fixed_camera', etc."""
        raise NotImplementedError
