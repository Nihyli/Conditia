"""Fleet-scoped integration tests exercising tenant isolation branches.

These tests run with JWT auth and a fleet-scoped principal, covering
the ``if principal.fleet_id is not None`` branches in routers that the
disabled-auth tests do not reach.
"""

from __future__ import annotations

import base64

import pytest
from httpx import AsyncClient

from config import settings
from database import SessionLocal
from domain import FleetRole
from models.db_models import (
    Fleet,
    FleetMembership,
    Inspection,
    InspectionMedia,
    Truck,
)
from tests.test_api import JWT_SECRET, mint_test_token

USER_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


async def _seed_scoped_fleet() -> dict[str, str]:
    async with SessionLocal() as db:
        fleet = Fleet(name="Scoped Fleet")
        db.add(fleet)
        await db.flush()
        db.add(
            FleetMembership(
                fleet_id=fleet.id, user_id=USER_A, role=FleetRole.ADMIN.value
            )
        )
        truck = Truck(fleet_id=fleet.id, vin="1FUJGLDR0CSBT0041")
        db.add(truck)
        await db.flush()
        inspection = Inspection(truck_id=truck.id, status="uploading")
        db.add(inspection)
        await db.flush()
        media = InspectionMedia(
            inspection_id=inspection.id,
            media_type="photo",
            capture_angle="front",
            capture_source="mobile",
            storage_path=f"{inspection.id}/front.png",
        )
        db.add(media)
        await db.commit()
        return {
            "fleet": fleet.id,
            "truck": truck.id,
            "inspection": inspection.id,
        }


@pytest.mark.asyncio
async def test_scoped_truck_crud(client: AsyncClient) -> None:
    original = (settings.auth_mode, settings.jwt_secret)
    settings.auth_mode = "jwt"
    settings.jwt_secret = JWT_SECRET
    try:
        ids = await _seed_scoped_fleet()
        headers = {"Authorization": f"Bearer {mint_test_token(USER_A)}"}

        trucks = await client.get("/trucks", headers=headers)
        assert trucks.status_code == 200
        assert len(trucks.json()) == 1
        assert trucks.json()[0]["fleet_id"] == ids["fleet"]

        truck_detail = await client.get(
            f"/trucks/{ids['truck']}", headers=headers
        )
        assert truck_detail.status_code == 200

        history = await client.get(
            f"/trucks/{ids['truck']}/inspections", headers=headers
        )
        assert history.status_code == 200
        assert len(history.json()) == 1

        created = await client.post(
            "/trucks",
            headers=headers,
            json={"vin": "1XKYDP9X7MJ000017"},
        )
        assert created.status_code == 201
        assert created.json()["fleet_id"] == ids["fleet"]
    finally:
        settings.auth_mode, settings.jwt_secret = original


@pytest.mark.asyncio
async def test_scoped_inspection_detail_and_upload(client: AsyncClient) -> None:
    original = (settings.auth_mode, settings.jwt_secret)
    settings.auth_mode = "jwt"
    settings.jwt_secret = JWT_SECRET
    try:
        ids = await _seed_scoped_fleet()
        headers = {"Authorization": f"Bearer {mint_test_token(USER_A)}"}

        inspections = await client.get("/inspections", headers=headers)
        assert inspections.status_code == 200
        assert len(inspections.json()) == 1

        detail = await client.get(
            f"/inspections/{ids['inspection']}", headers=headers
        )
        assert detail.status_code == 200

        coverage = await client.get(
            f"/inspections/{ids['inspection']}/coverage", headers=headers
        )
        assert coverage.status_code == 200
        assert "front" in coverage.json()["present"]

        findings = await client.get(
            f"/inspections/{ids['inspection']}/findings", headers=headers
        )
        assert findings.status_code == 200

        media = await client.get(
            f"/inspections/{ids['inspection']}/media", headers=headers
        )
        assert media.status_code == 200
        assert len(media.json()) == 1

        upload = await client.post(
            f"/inspections/{ids['inspection']}/upload",
            headers=headers,
            data={"capture_angle": "rear", "capture_source": "mobile"},
            files={"files": ("rear.png", PNG, "image/png")},
        )
        assert upload.status_code == 200
    finally:
        settings.auth_mode, settings.jwt_secret = original
