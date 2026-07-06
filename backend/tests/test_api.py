from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import event, func, select

from config import Settings, settings
from database import SessionLocal, engine
from domain import FleetRole
from models.db_models import (
    AnalysisJob,
    Finding,
    Fleet,
    FleetMembership,
    Inspection,
    InspectionMedia,
    Truck,
)
from services.analysis_jobs import resume_incomplete_analysis_jobs, run_analysis_job

JWT_SECRET = "test-jwt-secret-at-least-32-characters-long"
TEST_USER_ID = "22222222-2222-2222-2222-222222222222"


def mint_test_token(user_id: str = TEST_USER_ID) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": user_id,
            "aud": "authenticated",
            "iat": now,
            "exp": now + timedelta(hours=1),
        },
        JWT_SECRET,
        algorithm="HS256",
    )

VALID_TRUCK = {
    "vin": "1FUJGLDR0CSBT0041",
    "make": "Freightliner",
    "model": "Cascadia",
    "year": 2021,
    "license_plate": "TRK-041",
}
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


async def create_inspection(client: AsyncClient) -> str:
    truck_response = await client.post("/trucks", json=VALID_TRUCK)
    assert truck_response.status_code == 201, truck_response.text
    truck_id = truck_response.json()["id"]
    response = await client.post(
        "/inspections", json={"truck_id": truck_id, "capture_source": "mobile"}
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "uploading"
    return response.json()["id"]


async def upload_angle(client: AsyncClient, inspection_id: str, angle: str) -> None:
    response = await client.post(
        f"/inspections/{inspection_id}/upload",
        data={"capture_angle": angle, "capture_source": "mobile"},
        files={"files": (f"{angle}.png", PNG, "image/png")},
    )
    assert response.status_code == 200, response.text


async def upload_required_angles(client: AsyncClient, inspection_id: str) -> None:
    for angle in ("front", "rear", "driver_side", "passenger_side"):
        await upload_angle(client, inspection_id, angle)


@pytest.mark.asyncio
async def test_request_validation_and_bounded_lists(client: AsyncClient) -> None:
    readiness = await client.get("/ready")
    assert readiness.status_code == 200
    assert readiness.json()["status"] == "ready"

    invalid_vin = await client.post("/trucks", json={"vin": "short"})
    assert invalid_vin.status_code == 422

    excessive_limit = await client.get("/inspections?limit=1000")
    assert excessive_limit.status_code == 422
    assert (await client.get("/inspections/not-a-uuid")).status_code == 422

    oversized = await client.post(
        "/trucks",
        content=b"{}",
        headers={"Content-Length": str(settings.max_request_bytes + 1)},
    )
    assert oversized.status_code == 413
    assert oversized.headers["X-Content-Type-Options"] == "nosniff"
    assert oversized.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_duplicate_vin_is_a_safe_conflict(client: AsyncClient) -> None:
    assert (await client.post("/trucks", json=VALID_TRUCK)).status_code == 201
    duplicate = await client.post("/trucks", json=VALID_TRUCK)

    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "A truck with this VIN already exists"}


@pytest.mark.asyncio
async def test_upload_ignores_hostile_filename_and_does_not_analyze(
    client: AsyncClient,
) -> None:
    inspection_id = await create_inspection(client)
    response = await client.post(
        f"/inspections/{inspection_id}/upload",
        data={"capture_angle": "front", "capture_source": "mobile"},
        files={"files": ("../../../../main.py", PNG, "image/png")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "media_uploaded"
    async with SessionLocal() as db:
        inspection = await db.get(Inspection, inspection_id)
        assert inspection is not None
        assert inspection.status == "uploading"
        rows = await db.execute(
            InspectionMedia.__table__.select().where(
                InspectionMedia.inspection_id == inspection_id
            )
        )
        row = rows.first()
        stored_path = row.storage_path
        media_id = row.id
    assert "main.py" not in stored_path
    assert ".." not in Path(stored_path).parts
    delivered = await client.get(f"/inspection-media/{media_id}/content")
    assert delivered.status_code == 200
    assert delivered.content == PNG
    assert delivered.headers["Cache-Control"] == "private, no-store"


@pytest.mark.asyncio
async def test_invalid_media_is_rejected_without_database_row(
    client: AsyncClient,
) -> None:
    inspection_id = await create_inspection(client)
    response = await client.post(
        f"/inspections/{inspection_id}/upload",
        data={"capture_angle": "front", "capture_source": "mobile"},
        files={"files": ("fake.png", b"not an image", "image/png")},
    )

    assert response.status_code == 400
    async with SessionLocal() as db:
        count = await db.scalar(
            select(func.count())
            .select_from(InspectionMedia)
            .where(InspectionMedia.inspection_id == inspection_id)
        )
    assert count == 0


@pytest.mark.asyncio
async def test_finalize_requires_media_and_runs_only_once(client: AsyncClient) -> None:
    inspection_id = await create_inspection(client)
    empty = await client.post(f"/inspections/{inspection_id}/finalize")
    assert empty.status_code == 409

    await upload_angle(client, inspection_id, "front")
    incomplete = await client.post(f"/inspections/{inspection_id}/finalize")
    assert incomplete.status_code == 409
    assert "Missing required capture angles" in incomplete.json()["detail"]

    await upload_required_angles(client, inspection_id)

    coverage = await client.get(f"/inspections/{inspection_id}/coverage")
    assert coverage.status_code == 200
    assert coverage.json()["complete"] is True

    finalized = await client.post(f"/inspections/{inspection_id}/finalize")
    assert finalized.status_code == 200, finalized.text
    assert finalized.json()["status"] == "submitted"

    repeated = await client.post(f"/inspections/{inspection_id}/finalize")
    assert repeated.status_code == 409

    async with SessionLocal() as db:
        inspection = await db.get(Inspection, inspection_id)
        assert inspection is not None
        # No configured detector must never be reported as a successful clear result.
        assert inspection.status == "review_required"
        job = (
            await db.execute(
                select(AnalysisJob).where(AnalysisJob.inspection_id == inspection_id)
            )
        ).scalar_one()
        assert job.status == "complete"
        assert job.attempts == 1
        job_id = job.id

    # Duplicate delivery is idempotent and does not increment attempts.
    await run_analysis_job(job_id)
    async with SessionLocal() as db:
        assert (await db.get(AnalysisJob, job_id)).attempts == 1


@pytest.mark.asyncio
async def test_interrupted_analysis_job_is_reclaimed(client: AsyncClient) -> None:
    inspection_id = await create_inspection(client)
    uploaded = await client.post(
        f"/inspections/{inspection_id}/upload",
        data={"capture_angle": "front", "capture_source": "mobile"},
        files={"files": ("front.png", PNG, "image/png")},
    )
    assert uploaded.status_code == 200

    async with SessionLocal() as db:
        inspection = await db.get(Inspection, inspection_id)
        inspection.status = "processing"
        job = AnalysisJob(
            inspection_id=inspection_id,
            status="running",
            attempts=1,
        )
        db.add(job)
        await db.commit()
        job_id = job.id

    await resume_incomplete_analysis_jobs()

    async with SessionLocal() as db:
        inspection = await db.get(Inspection, inspection_id)
        job = await db.get(AnalysisJob, job_id)
        assert inspection.status == "review_required"
        assert job.status == "complete"
        assert job.attempts == 2


@pytest.mark.asyncio
async def test_running_job_with_valid_lease_is_not_reclaimed(
    client: AsyncClient,
) -> None:
    inspection_id = await create_inspection(client)

    async with SessionLocal() as db:
        inspection = await db.get(Inspection, inspection_id)
        inspection.status = "processing"
        job = AnalysisJob(
            inspection_id=inspection_id,
            status="running",
            attempts=1,
            lease_owner="another-live-instance",
            lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
        db.add(job)
        await db.commit()
        job_id = job.id

    await resume_incomplete_analysis_jobs()

    async with SessionLocal() as db:
        inspection = await db.get(Inspection, inspection_id)
        job = await db.get(AnalysisJob, job_id)
        # Untouched: another instance still holds a valid lease.
        assert inspection.status == "processing"
        assert job.status == "running"
        assert job.attempts == 1
        assert job.lease_owner == "another-live-instance"


@pytest.mark.asyncio
async def test_api_key_guard(client: AsyncClient) -> None:
    original_mode = settings.auth_mode
    original_key = settings.api_key
    settings.auth_mode = "api_key"
    settings.api_key = "a" * 32
    try:
        assert (await client.get("/trucks")).status_code == 401
        assert (
            await client.get("/trucks", headers={"X-API-Key": "wrong"})
        ).status_code == 401
        assert (
            await client.get("/trucks", headers={"X-API-Key": "a" * 32})
        ).status_code == 200
    finally:
        settings.auth_mode = original_mode
        settings.api_key = original_key


@pytest.mark.asyncio
async def test_api_key_fleet_scope_prevents_cross_fleet_reads(
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
        inspection_a = Inspection(truck_id=truck_a.id, status="uploading")
        inspection_b = Inspection(truck_id=truck_b.id, status="uploading")
        db.add_all((inspection_a, inspection_b))
        await db.commit()
        fleet_a_id = fleet_a.id
        truck_a_id = truck_a.id
        truck_b_id = truck_b.id
        inspection_a_id = inspection_a.id
        inspection_b_id = inspection_b.id

    original_mode = settings.auth_mode
    original_key = settings.api_key
    original_fleet = settings.api_fleet_id
    settings.auth_mode = "api_key"
    settings.api_key = "a" * 32
    settings.api_fleet_id = UUID(fleet_a_id)
    headers = {"X-API-Key": "a" * 32}
    try:
        response = await client.get("/trucks", headers=headers)
        assert response.status_code == 200
        assert [truck["id"] for truck in response.json()] == [truck_a_id]
        assert (await client.get(f"/trucks/{truck_b_id}", headers=headers)).status_code == 404
        inspections = await client.get("/inspections", headers=headers)
        assert [row["id"] for row in inspections.json()] == [inspection_a_id]
        assert (
            await client.get(f"/inspections/{inspection_b_id}", headers=headers)
        ).status_code == 404

        conflicting_create = await client.post(
            "/trucks",
            headers=headers,
            json={**VALID_TRUCK, "fleet_id": str(UUID(int=0))},
        )
        assert conflicting_create.status_code == 403
    finally:
        settings.auth_mode = original_mode
        settings.api_key = original_key
        settings.api_fleet_id = original_fleet


def test_production_settings_require_auth_fleet_and_private_media() -> None:
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            environment="production",
            auth_mode="disabled",
        )

    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            environment="production",
            auth_mode="api_key",
            api_key="a" * 32,
            api_fleet_id=None,
            database_url="postgresql+asyncpg://user:password@db.example/conditia",
            docs_enabled=False,
        )

    production = Settings(
        _env_file=None,
        environment="production",
        auth_mode="api_key",
        api_key="a" * 32,
        api_fleet_id=UUID(int=1),
        database_url="postgresql+asyncpg://user:password@db.example/conditia",
        storage_backend="supabase",
        supabase_url="https://example.supabase.co",
        supabase_key="service-role-key",
        docs_enabled=False,
        cors_origins="https://fleet.example.com",
    )
    assert production.environment == "production"

    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            environment="production",
            auth_mode="api_key",
            api_key="a" * 32,
            api_fleet_id=UUID(int=1),
            storage_backend="supabase",
            supabase_url="https://example.supabase.co",
            supabase_key="service-role-key",
            docs_enabled=False,
            cors_origins="https://fleet.example.com",
        )

    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            environment="production",
            auth_mode="api_key",
            api_key="a" * 32,
            api_fleet_id=UUID(int=1),
            database_url="postgresql+asyncpg://user:password@db.example/conditia",
            storage_backend="supabase",
            supabase_url="https://example.supabase.co",
            supabase_key="service-role-key",
            docs_enabled=False,
            cors_origins="https://fleet.example.com",
            seed_on_startup=True,
        )


@pytest.mark.asyncio
async def test_finding_resolution_updates_open_metric(client: AsyncClient) -> None:
    inspection_id = await create_inspection(client)
    async with SessionLocal() as db:
        finding = Finding(
            inspection_id=inspection_id,
            title="Test dent",
            finding_type="dent",
            severity="medium",
            confidence=0.8,
            status="open",
        )
        db.add(finding)
        await db.commit()
        finding_id = finding.id

    assert (await client.get("/fleet/stats")).json()["open_findings"] == 1
    resolved = await client.patch(
        f"/findings/{finding_id}",
        json={"status": "resolved", "resolution_notes": "Repaired"},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["resolved_at"] is not None
    assert (await client.get("/fleet/stats")).json()["open_findings"] == 0


@pytest.mark.asyncio
async def test_inspection_list_uses_bounded_query_count(client: AsyncClient) -> None:
    vins = (
        "1FUJGLDR0CSBT0041",
        "1XKYDP9X7MJ000017",
        "1XPBDP9X1ND000088",
    )
    for vin in vins:
        truck = await client.post("/trucks", json={"vin": vin})
        assert truck.status_code == 201
        inspection = await client.post(
            "/inspections",
            json={"truck_id": truck.json()["id"], "capture_source": "mobile"},
        )
        assert inspection.status_code == 201

    query_count = 0

    def count_query(*args) -> None:
        nonlocal query_count
        query_count += 1

    event.listen(engine.sync_engine, "before_cursor_execute", count_query)
    try:
        response = await client.get("/inspections")
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", count_query)

    assert response.status_code == 200
    assert len(response.json()) == 3
    assert query_count <= 5


@pytest.mark.asyncio
async def test_jwt_auth_requires_membership(client: AsyncClient) -> None:
    original_mode = settings.auth_mode
    original_secret = settings.jwt_secret
    settings.auth_mode = "jwt"
    settings.jwt_secret = JWT_SECRET
    token = mint_test_token()
    headers = {"Authorization": f"Bearer {token}"}
    try:
        assert (await client.get("/trucks", headers=headers)).status_code == 403
        assert (await client.get("/trucks")).status_code == 401

        async with SessionLocal() as db:
            fleet = Fleet(name="JWT Fleet")
            db.add(fleet)
            await db.flush()
            db.add(
                FleetMembership(
                    fleet_id=fleet.id,
                    user_id=TEST_USER_ID,
                    role=FleetRole.INSPECTOR.value,
                )
            )
            await db.commit()
            fleet_id = fleet.id

        me = await client.get("/auth/me", headers=headers)
        assert me.status_code == 200
        body = me.json()
        assert body["user_id"] == TEST_USER_ID
        assert body["fleet_id"] == fleet_id
        assert body["role"] == "inspector"

        trucks = await client.get("/trucks", headers=headers)
        assert trucks.status_code == 200
    finally:
        settings.auth_mode = original_mode
        settings.jwt_secret = original_secret


@pytest.mark.asyncio
async def test_viewer_cannot_register_trucks(client: AsyncClient) -> None:
    original_mode = settings.auth_mode
    original_secret = settings.jwt_secret
    settings.auth_mode = "jwt"
    settings.jwt_secret = JWT_SECRET
    headers = {"Authorization": f"Bearer {mint_test_token()}"}
    try:
        async with SessionLocal() as db:
            fleet = Fleet(name="Viewer Fleet")
            db.add(fleet)
            await db.flush()
            db.add(
                FleetMembership(
                    fleet_id=fleet.id,
                    user_id=TEST_USER_ID,
                    role=FleetRole.VIEWER.value,
                )
            )
            await db.commit()

        denied = await client.post("/trucks", headers=headers, json=VALID_TRUCK)
        assert denied.status_code == 403
    finally:
        settings.auth_mode = original_mode
        settings.jwt_secret = original_secret
