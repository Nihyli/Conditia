"""Contained, quota-aware local media storage for development deployments."""

from __future__ import annotations

import os
import tempfile
import warnings
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

import anyio
from fastapi import UploadFile

from config import settings

CHUNK_SIZE = 1024 * 1024


class StorageError(Exception):
    """Base class for safe storage failures."""


class InvalidStoragePath(StorageError):
    pass


class UnsupportedMedia(StorageError):
    pass


class UploadTooLarge(StorageError):
    pass


@dataclass(frozen=True)
class MediaFormat:
    content_type: str
    suffix: str
    media_type: str


@dataclass(frozen=True)
class StoredFile:
    storage_path: str
    media_type: str
    content_type: str
    size_bytes: int


def _sniff_media(header: bytes) -> MediaFormat:
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return MediaFormat("image/png", ".png", "photo")
    if header.startswith(b"\xff\xd8\xff"):
        return MediaFormat("image/jpeg", ".jpg", "photo")
    if header.startswith((b"GIF87a", b"GIF89a")):
        return MediaFormat("image/gif", ".gif", "photo")
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return MediaFormat("image/webp", ".webp", "photo")
    if header.startswith(b"\x1aE\xdf\xa3"):
        return MediaFormat("video/webm", ".webm", "video")
    if len(header) >= 12 and header[4:8] == b"ftyp":
        major_brand = header[8:12]
        if major_brand == b"qt  ":
            return MediaFormat("video/quicktime", ".mov", "video")
        return MediaFormat("video/mp4", ".mp4", "video")
    raise UnsupportedMedia("Unsupported or invalid image/video content")


class LocalStorageService:
    def __init__(self, base_dir: str, max_upload_bytes: int | None = None) -> None:
        self.base = Path(base_dir).resolve()
        self.max_upload_bytes = max_upload_bytes or settings.max_upload_bytes
        self.base.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        candidate = (self.base / path).resolve()
        if not candidate.is_relative_to(self.base):
            raise InvalidStoragePath("Storage path escapes configured root")
        return candidate

    def _write_upload(
        self,
        source: BinaryIO,
        inspection_id: str,
        capture_angle: str,
    ) -> StoredFile:
        header = source.read(CHUNK_SIZE)
        if not header:
            raise UnsupportedMedia("Empty uploads are not allowed")
        media_format = _sniff_media(header)

        relative = (
            Path(inspection_id)
            / capture_angle
            / f"{uuid4().hex}{media_format.suffix}"
        ).as_posix()
        destination = self._resolve(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.uploading")

        size = 0
        try:
            with temporary.open("xb") as output:
                chunk = header
                while chunk:
                    size += len(chunk)
                    if size > self.max_upload_bytes:
                        raise UploadTooLarge(
                            f"Upload exceeds {self.max_upload_bytes} byte limit"
                        )
                    output.write(chunk)
                    chunk = source.read(CHUNK_SIZE)
                output.flush()
                os.fsync(output.fileno())
            if media_format.media_type == "photo":
                self._verify_image(temporary)
            os.replace(temporary, destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

        return StoredFile(
            storage_path=relative,
            media_type=media_format.media_type,
            content_type=media_format.content_type,
            size_bytes=size,
        )

    def _verify_image(self, path: Path) -> None:
        from PIL import Image, UnidentifiedImageError

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(path) as image:
                    width, height = image.size
                    if width * height > settings.max_image_pixels:
                        raise UnsupportedMedia("Image dimensions exceed the limit")
                    image.verify()
        except UnsupportedMedia:
            raise
        except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
            raise UnsupportedMedia("Image content could not be decoded") from exc

    async def upload(
        self,
        file: UploadFile,
        inspection_id: str,
        capture_angle: str,
    ) -> StoredFile:
        await file.seek(0)
        return await anyio.to_thread.run_sync(
            self._write_upload,
            file.file,
            inspection_id,
            capture_angle,
        )

    async def download(self, path: str) -> bytes:
        return await anyio.to_thread.run_sync(self._resolve(path).read_bytes)

    async def delete(self, path: str) -> None:
        try:
            await anyio.to_thread.run_sync(self._resolve(path).unlink, True)
        except OSError as exc:
            raise StorageError("Stored media could not be removed") from exc

    def abs_path(self, path: str) -> Path:
        return self._resolve(path)

    def local_path(self, path: str) -> Path:
        return self._resolve(path)

    @asynccontextmanager
    async def materialize(self, path: str) -> AsyncIterator[Path]:
        yield self._resolve(path)

    async def delivery_url(self, path: str, expires_in: int = 60) -> str | None:
        del expires_in
        self._resolve(path)
        return None


class SupabaseStorageService:
    """Private Supabase bucket implementation using server-side credentials."""

    def __init__(
        self,
        url: str,
        key: str,
        bucket: str,
        max_upload_bytes: int | None = None,
    ) -> None:
        from supabase import create_client

        self.bucket = create_client(url, key).storage.from_(bucket)
        self.max_upload_bytes = max_upload_bytes or settings.max_upload_bytes

    def _upload(
        self,
        source: BinaryIO,
        inspection_id: str,
        capture_angle: str,
    ) -> StoredFile:
        with tempfile.TemporaryDirectory(prefix="conditia-upload-") as directory:
            staging = LocalStorageService(directory, self.max_upload_bytes)
            result = staging._write_upload(source, inspection_id, capture_angle)
            with staging.local_path(result.storage_path).open("rb") as payload:
                self.bucket.upload(
                    path=result.storage_path,
                    file=payload,
                    file_options={
                        "cache-control": "3600",
                        "content-type": result.content_type,
                        "upsert": "false",
                    },
                )
            return result

    async def upload(
        self,
        file: UploadFile,
        inspection_id: str,
        capture_angle: str,
    ) -> StoredFile:
        await file.seek(0)
        try:
            return await anyio.to_thread.run_sync(
                self._upload,
                file.file,
                inspection_id,
                capture_angle,
            )
        except (UnsupportedMedia, UploadTooLarge):
            raise
        except Exception as exc:
            raise StorageError("Object storage upload failed") from exc

    async def download(self, path: str) -> bytes:
        try:
            return await anyio.to_thread.run_sync(self.bucket.download, path)
        except Exception as exc:
            raise StorageError("Object storage download failed") from exc

    async def delete(self, path: str) -> None:
        try:
            await anyio.to_thread.run_sync(self.bucket.remove, [path])
        except Exception as exc:
            raise StorageError("Stored media could not be removed") from exc

    @asynccontextmanager
    async def materialize(self, path: str) -> AsyncIterator[Path]:
        content = await self.download(path)
        suffix = Path(path).suffix
        descriptor, temporary_name = tempfile.mkstemp(
            prefix="conditia-media-",
            suffix=suffix,
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            await anyio.to_thread.run_sync(temporary.write_bytes, content)
            yield temporary
        finally:
            await anyio.to_thread.run_sync(temporary.unlink, True)

    async def delivery_url(self, path: str, expires_in: int = 60) -> str | None:
        try:
            response = await anyio.to_thread.run_sync(
                self.bucket.create_signed_url,
                path,
                expires_in,
            )
        except Exception as exc:
            raise StorageError("Could not create media delivery URL") from exc
        if isinstance(response, dict):
            url = response.get("signedURL") or response.get("signedUrl")
            if isinstance(url, str):
                return url
        raise StorageError("Object storage returned an invalid signed URL")


def create_storage_service():
    if settings.storage_backend == "supabase":
        if not settings.supabase_url or not settings.supabase_key:
            raise RuntimeError("Supabase storage credentials are required")
        return SupabaseStorageService(
            settings.supabase_url,
            settings.supabase_key,
            settings.supabase_storage_bucket,
        )
    return LocalStorageService(settings.storage_dir)


storage_service = create_storage_service()
