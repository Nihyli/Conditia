from fastapi import UploadFile

from adapters.base import CaptureAdapter, CaptureMetadata, StoredMedia
from services.storage import storage_service


class MobileAdapter(CaptureAdapter):
    """MVP capture adapter.

    Accepts video/photo from a phone browser via the MediaRecorder API.
    No special hardware, no SDK, no configuration required.
    """

    def get_source_name(self) -> str:
        return "mobile"

    async def receive_media(
        self,
        inspection_id: str,
        files: list[UploadFile],
        capture_angle: str,
        metadata: CaptureMetadata,
    ) -> list[StoredMedia]:
        stored: list[StoredMedia] = []
        try:
            for file in files:
                result = await storage_service.upload(
                    file=file,
                    inspection_id=inspection_id,
                    capture_angle=capture_angle,
                )
                stored.append(
                    StoredMedia(
                        storage_path=result.storage_path,
                        media_type=result.media_type,
                        content_type=result.content_type,
                        size_bytes=result.size_bytes,
                    )
                )
            return stored
        except Exception:
            for item in stored:
                await storage_service.delete(item.storage_path)
            raise
