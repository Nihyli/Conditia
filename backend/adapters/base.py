from abc import ABC, abstractmethod

from fastapi import UploadFile


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
        metadata: dict,
    ) -> list[str]:
        """Accept raw media, store it, return storage paths.

        `metadata` holds source-specific fields:
          - mobile: { gps_lat, gps_lng }
          - drone:  { drone_flight_id, gps_lat, gps_lng, altitude, heading }
        """
        raise NotImplementedError

    @abstractmethod
    def get_source_name(self) -> str:
        """Return 'mobile', 'drone', 'fixed_camera', etc."""
        raise NotImplementedError
