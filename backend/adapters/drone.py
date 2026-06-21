from fastapi import UploadFile

from adapters.base import CaptureAdapter, CaptureMetadata, StoredMedia


class DroneAdapter(CaptureAdapter):
    """Phase 5: DJI SDK integration.

    When implemented, this receives media pulled from a DJI drone via the DJI
    Mobile SDK and populates drone-specific metadata (flight_id, GPS from drone
    telemetry, altitude, heading). Everything downstream is identical to mobile
    captures -- zero changes to analysis, schema, or dashboard.

    Stub until Phase 5.
    """

    def get_source_name(self) -> str:
        return "drone"

    async def receive_media(
        self,
        inspection_id: str,
        files: list[UploadFile],
        capture_angle: str,
        metadata: CaptureMetadata,
    ) -> list[StoredMedia]:
        raise NotImplementedError("Drone adapter -- Phase 5")
