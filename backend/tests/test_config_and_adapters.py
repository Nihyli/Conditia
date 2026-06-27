from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from uuid import UUID

import pytest
from fastapi import UploadFile
from pydantic import ValidationError

from adapters.base import CaptureMetadata
from adapters.mobile import MobileAdapter
from adapters.registry import CaptureAdapterRegistry
from config import Settings
from domain import IngestibleCaptureSource
from models.schemas import FindingUpdate, TruckCreate
from services.storage import StoredFile
from utils import normalize_severity, worst_severity


def production_settings(**overrides) -> dict:
    values = {
        "_env_file": None,
        "environment": "production",
        "auth_mode": "api_key",
        "api_key": "a" * 32,
        "api_fleet_id": UUID(int=1),
        "database_url": "postgresql+asyncpg://user:password@db.example/conditia",
        "storage_backend": "supabase",
        "supabase_url": "https://example.supabase.co",
        "supabase_key": "service-role-key",
        "docs_enabled": False,
        "cors_origins": "https://fleet.example.com",
    }
    values.update(overrides)
    return values


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"auth_mode": "api_key", "api_key": "short"}, "at least 32"),
        ({"max_upload_bytes": 0}, "must be positive"),
        (
            {"max_upload_bytes": 20, "max_request_bytes": 10},
            "cannot be smaller",
        ),
        ({"max_files_per_upload": 0}, "between 1 and 20"),
        ({"max_files_per_upload": 21}, "between 1 and 20"),
        ({"max_image_pixels": 0}, "must be positive"),
    ],
)
def test_settings_reject_invalid_limits(overrides, message) -> None:
    with pytest.raises(ValueError, match=message):
        Settings(_env_file=None, **overrides)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"database_url": "sqlite+aiosqlite:///local.db"}, "PostgreSQL"),
        ({"storage_backend": "local"}, "Supabase storage"),
        ({"seed_on_startup": True}, "SEED_ON_STARTUP"),
        ({"docs_enabled": True}, "DOCS_ENABLED"),
        ({"api_fleet_id": None}, "API_FLEET_ID"),
        ({"cors_origins": "http://localhost:5173"}, "deployed origins"),
    ],
)
def test_production_settings_fail_closed(overrides, message) -> None:
    with pytest.raises(ValueError, match=message):
        Settings(**production_settings(**overrides))


def test_settings_properties_and_schema_normalization() -> None:
    settings = Settings(
        _env_file=None,
        cors_origins=" https://one.example,https://two.example, ",
        google_application_credentials="credentials.json",
        supabase_url="https://example.supabase.co",
        supabase_key="key",
    )
    truck = TruckCreate(
        vin=" 1fujgldr0csbt0041 ",
        make=" ",
        model=" VNL ",
        license_plate=" TRK-1 ",
    )

    assert settings.cors_list == ["https://one.example", "https://two.example"]
    assert settings.google_vision_enabled is True
    assert settings.supabase_enabled is True
    assert truck.vin == "1FUJGLDR0CSBT0041"
    assert truck.make is None
    assert truck.model == "VNL"
    assert truck.license_plate == "TRK-1"

    with pytest.raises(ValidationError):
        TruckCreate(
            vin="1FUJGLDR0CSBT0041",
            year=datetime.now(timezone.utc).year + 2,
        )
    with pytest.raises(ValidationError):
        FindingUpdate(status="resolved", resolution_notes="x" * 1001)


def test_severity_helpers() -> None:
    assert normalize_severity("high") == "critical"
    assert normalize_severity("low") == "low"
    assert worst_severity([]) == "clear"
    assert worst_severity(["unknown", "low", "high"]) == "critical"


@pytest.mark.asyncio
async def test_mobile_adapter_returns_typed_media() -> None:
    class Storage:
        async def upload(self, **kwargs):
            assert kwargs["inspection_id"] == "inspection"
            return StoredFile("stored/photo.png", "photo", "image/png", 10)

        async def delete(self, path):
            raise AssertionError(f"unexpected cleanup: {path}")

    file = UploadFile(filename="hostile.png", file=BytesIO(b"payload"))
    adapter = MobileAdapter(Storage())

    result = await adapter.receive_media(
        "inspection", [file], "front", CaptureMetadata()
    )

    assert adapter.get_source_name() == "mobile"
    assert result[0].storage_path == "stored/photo.png"
    assert result[0].size_bytes == 10
    registry = CaptureAdapterRegistry({IngestibleCaptureSource.MOBILE: adapter})
    assert registry.get(IngestibleCaptureSource.MOBILE) is adapter


@pytest.mark.asyncio
async def test_mobile_adapter_cleans_up_partial_upload() -> None:
    deleted: list[str] = []

    class Storage:
        calls = 0

        async def upload(self, **kwargs):
            del kwargs
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("storage failed")
            return StoredFile("stored/first.png", "photo", "image/png", 10)

        async def delete(self, path):
            deleted.append(path)

    files = [
        UploadFile(filename="one.png", file=BytesIO(b"one")),
        UploadFile(filename="two.png", file=BytesIO(b"two")),
    ]

    with pytest.raises(RuntimeError, match="storage failed"):
        await MobileAdapter(Storage()).receive_media(
            "inspection", files, "front", CaptureMetadata()
        )
    assert deleted == ["stored/first.png"]
