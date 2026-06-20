"""Media storage.

Local disk implementation for dev (zero setup). The interface mirrors what a
Supabase Storage implementation would expose, so swapping is a one-file change.
"""

from pathlib import Path

from fastapi import UploadFile

from config import settings


class LocalStorageService:
    def __init__(self, base_dir: str) -> None:
        self.base = Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)

    async def upload(self, file: UploadFile, path: str) -> str:
        dest = self.base / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        content = await file.read()
        dest.write_bytes(content)
        return path

    async def write_bytes(self, data: bytes, path: str) -> str:
        dest = self.base / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return path

    async def download(self, path: str) -> bytes:
        return (self.base / path).read_bytes()

    def abs_path(self, path: str) -> Path:
        return self.base / path

    def public_url(self, path: str) -> str:
        return f"/media/{path}"


storage_service = LocalStorageService(settings.storage_dir)
