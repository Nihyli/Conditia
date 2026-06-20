from fastapi import UploadFile

from adapters.base import CaptureAdapter
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
        metadata: dict,
    ) -> list[str]:
        paths: list[str] = []
        for file in files:
            filename = file.filename or "capture.bin"
            path = await storage_service.upload(
                file=file,
                path=f"{inspection_id}/{capture_angle}/{filename}",
            )
            paths.append(path)
        return paths
