from __future__ import annotations

import base64
from io import BytesIO

import pytest

from services.storage import (
    InvalidStoragePath,
    LocalStorageService,
    SupabaseStorageService,
    UnsupportedMedia,
    UploadTooLarge,
)

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def test_storage_rejects_paths_outside_root(tmp_path) -> None:
    storage = LocalStorageService(str(tmp_path))

    with pytest.raises(InvalidStoragePath):
        storage.abs_path("../../application.py")


def test_storage_generates_server_owned_contained_name(tmp_path) -> None:
    storage = LocalStorageService(str(tmp_path))

    result = storage._write_upload(BytesIO(PNG), "inspection-id", "front")

    resolved = storage.abs_path(result.storage_path)
    assert resolved.is_relative_to(tmp_path.resolve())
    assert resolved.name.endswith(".png")
    assert resolved.read_bytes() == PNG
    assert result.media_type == "photo"


def test_storage_rejects_invalid_and_oversized_media(tmp_path) -> None:
    storage = LocalStorageService(str(tmp_path))

    with pytest.raises(UnsupportedMedia):
        storage._write_upload(BytesIO(b"not media"), "inspection-id", "front")

    with pytest.raises(UnsupportedMedia):
        storage._write_upload(
            BytesIO(b"\x89PNG\r\n\x1a\nnot-really-an-image"),
            "inspection-id",
            "front",
        )

    limited_storage = LocalStorageService(str(tmp_path), max_upload_bytes=10)
    with pytest.raises(UploadTooLarge):
        limited_storage._write_upload(BytesIO(PNG), "inspection-id", "front")

    assert not list(tmp_path.rglob("*.uploading"))


class FakeBucket:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def upload(self, *, path, file, file_options) -> None:
        assert file_options["upsert"] == "false"
        self.objects[path] = file.read()

    def download(self, path) -> bytes:
        return self.objects[path]

    def remove(self, paths) -> None:
        for path in paths:
            self.objects.pop(path, None)

    def create_signed_url(self, path, expires_in):
        return {"signedURL": f"https://storage.example/{path}?ttl={expires_in}"}


@pytest.mark.asyncio
async def test_supabase_storage_uses_validated_private_objects() -> None:
    service = object.__new__(SupabaseStorageService)
    service.bucket = FakeBucket()
    service.max_upload_bytes = 1024

    stored = service._upload(BytesIO(PNG), "inspection-id", "front")
    assert service.bucket.objects[stored.storage_path] == PNG
    assert await service.download(stored.storage_path) == PNG
    assert (await service.delivery_url(stored.storage_path)).startswith(
        "https://storage.example/"
    )

    await service.delete(stored.storage_path)
    assert service.bucket.objects == {}
