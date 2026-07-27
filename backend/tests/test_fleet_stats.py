"""Tests for routers/fleet.py – fleet stats counters."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from config import settings
from database import SessionLocal
from models.db_models import Finding, Fleet, FleetMembership, Inspection, Truck
from tests.test_api import JWT_SECRET, mint_test_token

USER_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


async def _seed_fleet_with_data() -> str:
    """Create a fleet with trucks, inspections at various statuses, and a finding."""
    async with SessionLocal() as db:
        fleet = Fleet(name="Stats Fleet")
        db.add(fleet)
        await db.flush()
        db.add(
            FleetMembership(
                fleet_id=fleet.id, user_id=USER_A, role="admin"
            )
        )
        truck = Truck(fleet_id=fleet.id, vin="1FUJGLDR0CSBT0041")
        db.add(truck)
        await db.flush()

        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)

        uploading = Inspection(
            truck_id=truck.id, status="uploading", started_at=now
        )
        submitted = Inspection(
            truck_id=truck.id, status="submitted", started_at=now
        )
        complete_today = Inspection(
            truck_id=truck.id, status="complete", started_at=now
        )
        complete_yesterday = Inspection(
            truck_id=truck.id, status="complete", started_at=yesterday
        )
        db.add_all([uploading, submitted, complete_today, complete_yesterday])
        await db.flush()

        db.add(
            Finding(
                inspection_id=complete_today.id,
                finding_type="dent",
                severity="medium",
                confidence=0.9,
                status="open",
            )
        )
        await db.commit()
        return fleet.id


@pytest.mark.asyncio
async def test_fleet_stats_all_counters_scoped(client: AsyncClient) -> None:
    original = (settings.auth_mode, settings.jwt_secret)
    settings.auth_mode = "jwt"
    settings.jwt_secret = JWT_SECRET
    try:
        await _seed_fleet_with_data()
        headers = {"Authorization": f"Bearer {mint_test_token(USER_A)}"}
        response = await client.get("/fleet/stats", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["active_trucks"] == 1
        assert data["inspections_today"] >= 3
        assert data["inspections_pending"] == 2  # uploading + submitted
        assert data["inspections_complete_today"] == 1
        assert data["open_findings"] == 1
    finally:
        settings.auth_mode, settings.jwt_secret = original


@pytest.mark.asyncio
async def test_fleet_stats_unscoped_disabled_auth(client: AsyncClient) -> None:
    await _seed_fleet_with_data()
    response = await client.get("/fleet/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["active_trucks"] >= 1
    assert data["open_findings"] >= 1


@pytest.mark.asyncio
async def test_fleet_stats_scoped_isolates_other_fleets(
    client: AsyncClient,
) -> None:
    original = (settings.auth_mode, settings.jwt_secret)
    settings.auth_mode = "jwt"
    settings.jwt_secret = JWT_SECRET
    try:
        async with SessionLocal() as db:
            fleet = Fleet(name="Empty Fleet")
            db.add(fleet)
            await db.flush()
            db.add(
                FleetMembership(
                    fleet_id=fleet.id, user_id=USER_A, role="admin"
                )
            )
            await db.commit()
            fleet_id = fleet.id

        headers = {"Authorization": f"Bearer {mint_test_token(USER_A)}"}
        response = await client.get(
            "/fleet/stats", headers={**headers, "X-Fleet-ID": fleet_id}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["active_trucks"] == 0
        assert data["inspections_today"] == 0
        assert data["inspections_pending"] == 0
        assert data["inspections_complete_today"] == 0
        assert data["open_findings"] == 0
    finally:
        settings.auth_mode, settings.jwt_secret = original
