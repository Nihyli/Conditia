from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import anyio
import pytest
from httpx import AsyncClient

import routers.media as media_router
from config import settings
from database import SessionLocal
from models.db_models import Finding, Fleet, Inspection, InspectionMedia, Report, Truck
from services.storage import StorageError, storage_service


def write_file(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


async def persisted_inspection() -> dict[str, str]:
    async with SessionLocal() as db:
        truck = Truck(
            vin="1FUJGLDR0CSBT0041",
            make="Volvo",
            model="VNL",
            license_plate="TRK-001",
        )
        db.add(truck)
        await db.flush()
        inspection = Inspection(truck_id=truck.id, status="complete")
        db.add(inspection)
        await db.flush()
        media = InspectionMedia(
            inspection_id=inspection.id,
            media_type="photo",
            capture_angle="front",
            capture_source="mobile",
            storage_path=f"{inspection.id}/front/evidence.png",
        )
        db.add(media)
        await db.flush()
        finding = Finding(
            inspection_id=inspection.id,
            media_id=media.id,
            title="Bumper dent",
            finding_type="dent",
            severity="medium",
            confidence=0.82,
            status="open",
            zone="front",
        )
        report = Report(
            inspection_id=inspection.id,
            summary="One finding",
            total_findings=1,
            critical_findings=0,
        )
        db.add_all((finding, report))
        await db.commit()
        return {
            "truck": truck.id,
            "inspection": inspection.id,
            "media": media.id,
            "finding": finding.id,
        }


@pytest.mark.asyncio
async def test_read_routes_and_finding_lifecycle(client: AsyncClient) -> None:
    ids = await persisted_inspection()

    assert (await client.get(f"/trucks/{ids['truck']}")).status_code == 200
    truck_history = await client.get(f"/trucks/{ids['truck']}/inspections")
    assert [item["id"] for item in truck_history.json()] == [ids["inspection"]]

    detail = await client.get(f"/inspections/{ids['inspection']}")
    assert detail.status_code == 200
    assert detail.json()["finding_count"] == 1
    assert detail.json()["media"][0]["id"] == ids["media"]

    inspection_findings = await client.get(
        f"/inspections/{ids['inspection']}/findings"
    )
    inspection_media = await client.get(f"/inspections/{ids['inspection']}/media")
    assert inspection_findings.json()[0]["id"] == ids["finding"]
    assert inspection_media.json()[0]["capture_angle"] == "front"

    findings = await client.get("/findings?severity=medium&status=open")
    assert [item["id"] for item in findings.json()] == [ids["finding"]]
    assert (await client.get("/findings?severity=critical")).json() == []

    acknowledged = await client.patch(
        f"/findings/{ids['finding']}",
        json={"status": "acknowledged", "resolution_notes": "Scheduled"},
    )
    assert acknowledged.json()["status"] == "acknowledged"
    assert acknowledged.json()["resolved_at"] is None

    false_positive = await client.patch(
        f"/findings/{ids['finding']}",
        json={"status": "false_positive", "resolution_notes": "Reflection"},
    )
    assert false_positive.json()["resolved_at"] is not None

    reports = await client.get("/reports")
    report = await client.get(f"/reports/{ids['inspection']}")
    assert reports.json()[0]["summary"] == "One finding"
    assert report.json()["inspection_id"] == ids["inspection"]


@pytest.mark.asyncio
async def test_not_found_and_validation_paths(client: AsyncClient) -> None:
    missing = str(uuid4())
    assert (await client.get(f"/trucks/{missing}")).status_code == 404
    assert (await client.get(f"/trucks/{missing}/inspections")).status_code == 404
    assert (await client.get(f"/inspections/{missing}")).status_code == 404
    assert (await client.get(f"/inspections/{missing}/findings")).status_code == 404
    assert (await client.get(f"/inspections/{missing}/media")).status_code == 404
    assert (await client.get(f"/reports/{missing}")).status_code == 404
    assert (await client.get(f"/inspection-media/{missing}/content")).status_code == 404
    assert (await client.patch(
        f"/findings/{missing}", json={"status": "resolved"}
    )).status_code == 404

    missing_fleet = await client.post(
        "/trucks",
        json={"vin": "1FUJGLDR0CSBT0041", "fleet_id": missing},
    )
    assert missing_fleet.status_code == 404
    missing_truck = await client.post(
        "/inspections",
        json={"truck_id": missing, "capture_source": "mobile"},
    )
    assert missing_truck.status_code == 404
    assert (await client.get("/reports?limit=0")).status_code == 422
    assert (await client.get("/findings?status=invalid")).status_code == 422


@pytest.mark.asyncio
async def test_upload_route_rejects_invalid_metadata_and_closed_inspections(
    client: AsyncClient,
) -> None:
    ids = await persisted_inspection()
    png = b"\x89PNG\r\n\x1a\ninvalid-but-not-reached"
    closed = await client.post(
        f"/inspections/{ids['inspection']}/upload",
        data={"capture_angle": "front", "capture_source": "mobile"},
        files={"files": ("front.png", png, "image/png")},
    )
    assert closed.status_code == 409

    async with SessionLocal() as db:
        inspection = await db.get(Inspection, ids["inspection"])
        inspection.status = "uploading"
        await db.commit()

    bad_latitude = await client.post(
        f"/inspections/{ids['inspection']}/upload",
        data={
            "capture_angle": "front",
            "capture_source": "mobile",
            "gps_lat": "91",
        },
        files={"files": ("front.png", png, "image/png")},
    )
    assert bad_latitude.status_code == 422

    too_many = await client.post(
        f"/inspections/{ids['inspection']}/upload",
        data={"capture_angle": "front", "capture_source": "mobile"},
        files=[("files", (f"{index}.png", png, "image/png")) for index in range(7)],
    )
    assert too_many.status_code == 413


@pytest.mark.asyncio
async def test_media_delivery_redirect_and_safe_failures(
    client: AsyncClient,
    monkeypatch,
) -> None:
    ids = await persisted_inspection()

    class SignedStorage:
        async def delivery_url(self, path):
            assert path.endswith("evidence.png")
            return "https://storage.example/signed"

    monkeypatch.setattr(media_router, "storage_service", SignedStorage())
    redirect = await client.get(
        f"/inspection-media/{ids['media']}/content",
        follow_redirects=False,
    )
    assert redirect.status_code == 307
    assert redirect.headers["location"] == "https://storage.example/signed"

    class FailingStorage:
        async def delivery_url(self, path):
            del path
            raise StorageError("private detail")

    monkeypatch.setattr(media_router, "storage_service", FailingStorage())
    unavailable = await client.get(f"/inspection-media/{ids['media']}/content")
    assert unavailable.status_code == 503
    assert unavailable.json() == {"detail": "Media is temporarily unavailable"}

    class UnconfiguredStorage:
        async def delivery_url(self, path):
            del path
            return None

    monkeypatch.setattr(media_router, "storage_service", UnconfiguredStorage())
    assert (
        await client.get(f"/inspection-media/{ids['media']}/content")
    ).status_code == 503


@pytest.mark.asyncio
async def test_local_media_delivery_keeps_content_private(client: AsyncClient) -> None:
    ids = await persisted_inspection()
    media_path = storage_service.abs_path(f"{ids['inspection']}/front/evidence.png")
    await anyio.to_thread.run_sync(write_file, Path(media_path), b"image")

    response = await client.get(f"/inspection-media/{ids['media']}/content")
    assert response.status_code == 200
    assert response.content == b"image"
    assert response.headers["Cache-Control"] == "private, no-store"


@pytest.mark.asyncio
async def test_fleet_scope_applies_to_findings_reports_stats_and_media(
    client: AsyncClient,
) -> None:
    async with SessionLocal() as db:
        fleet_a = Fleet(name="Fleet A")
        fleet_b = Fleet(name="Fleet B")
        db.add_all((fleet_a, fleet_b))
        await db.flush()
        truck_a = Truck(fleet_id=fleet_a.id, vin="1FUJGLDR0CSBT0041")
        truck_b = Truck(fleet_id=fleet_b.id, vin="1XKYDP9X7MJ000017")
        db.add_all((truck_a, truck_b))
        await db.flush()
        inspection_a = Inspection(truck_id=truck_a.id, status="complete")
        inspection_b = Inspection(truck_id=truck_b.id, status="complete")
        db.add_all((inspection_a, inspection_b))
        await db.flush()
        media_a = InspectionMedia(
            inspection_id=inspection_a.id,
            media_type="photo",
            capture_angle="front",
            storage_path="a/front.png",
        )
        media_b = InspectionMedia(
            inspection_id=inspection_b.id,
            media_type="photo",
            capture_angle="front",
            storage_path="b/front.png",
        )
        db.add_all((media_a, media_b))
        await db.flush()
        finding_a = Finding(
            inspection_id=inspection_a.id,
            finding_type="dent",
            severity="medium",
            confidence=0.8,
            status="open",
        )
        finding_b = Finding(
            inspection_id=inspection_b.id,
            finding_type="dent",
            severity="medium",
            confidence=0.8,
            status="open",
        )
        report_a = Report(inspection_id=inspection_a.id)
        report_b = Report(inspection_id=inspection_b.id)
        db.add_all((finding_a, finding_b, report_a, report_b))
        await db.commit()
        fleet_a_id = fleet_a.id
        finding_a_id = finding_a.id
        finding_b_id = finding_b.id
        inspection_b_id = inspection_b.id
        media_b_id = media_b.id

    original = (settings.auth_mode, settings.api_key, settings.api_fleet_id)
    settings.auth_mode = "api_key"
    settings.api_key = "a" * 32
    settings.api_fleet_id = UUID(fleet_a_id)
    headers = {"X-API-Key": "a" * 32}
    try:
        findings = await client.get("/findings", headers=headers)
        reports = await client.get("/reports", headers=headers)
        stats = await client.get("/fleet/stats", headers=headers)
        assert [item["id"] for item in findings.json()] == [finding_a_id]
        assert [item["inspection_id"] for item in reports.json()] == [
            inspection_a.id
        ]
        assert stats.json()["active_trucks"] == 1
        assert stats.json()["open_findings"] == 1
        assert (
            await client.patch(
                f"/findings/{finding_b_id}",
                headers=headers,
                json={"status": "resolved"},
            )
        ).status_code == 404
        assert (
            await client.get(f"/reports/{inspection_b_id}", headers=headers)
        ).status_code == 404
        assert (
            await client.get(
                f"/inspection-media/{media_b_id}/content", headers=headers
            )
        ).status_code == 404
    finally:
        settings.auth_mode, settings.api_key, settings.api_fleet_id = original
