from fastapi import UploadFile

from adapters.base import CaptureAdapter, CaptureMetadata, MediaWriter, StoredMedia


class MobileAdapter(CaptureAdapter):
    """MVP capture adapter.

    Accepts video/photo from a phone browser via the MediaRecorder API.
    No special hardware, no SDK, no configuration required.
    """

    def get_source_name(self) -> str:
        return "mobile"

    def __init__(self, storage: MediaWriter) -> None:
        self._storage = storage

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
                result = await self._storage.upload(
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
                await self._storage.delete(item.storage_path)
            raise
