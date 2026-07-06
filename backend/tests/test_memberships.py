import pytest
from httpx import AsyncClient

from config import settings
from database import SessionLocal
from domain import FleetRole
from models.db_models import Fleet, FleetMembership
from tests.test_api import JWT_SECRET, TEST_USER_ID, mint_test_token

ADMIN_USER = "33333333-3333-3333-3333-333333333333"
OTHER_USER = "44444444-4444-4444-4444-444444444444"


async def seed_admin_fleet() -> str:
    async with SessionLocal() as db:
        fleet = Fleet(name="Members Fleet")
        db.add(fleet)
        await db.flush()
        db.add(
            FleetMembership(
                fleet_id=fleet.id,
                user_id=ADMIN_USER,
                role=FleetRole.ADMIN.value,
            )
        )
        await db.commit()
        return fleet.id


@pytest.mark.asyncio
async def test_fleet_member_crud(client: AsyncClient) -> None:
    original_mode = settings.auth_mode
    original_secret = settings.jwt_secret
    settings.auth_mode = "jwt"
    settings.jwt_secret = JWT_SECRET
    fleet_id = await seed_admin_fleet()
    headers = {"Authorization": f"Bearer {mint_test_token(ADMIN_USER)}"}
    try:
        listed = await client.get("/fleet/members", headers=headers)
        assert listed.status_code == 200
        assert len(listed.json()) == 1

        created = await client.post(
            "/fleet/members",
            headers=headers,
            json={"user_id": OTHER_USER, "role": "inspector"},
        )
        assert created.status_code == 201
        assert created.json()["role"] == "inspector"
        assert created.json()["fleet_id"] == fleet_id

        updated = await client.patch(
            f"/fleet/members/{OTHER_USER}",
            headers=headers,
            json={"role": "viewer"},
        )
        assert updated.status_code == 200
        assert updated.json()["role"] == "viewer"

        removed = await client.delete(
            f"/fleet/members/{OTHER_USER}",
            headers=headers,
        )
        assert removed.status_code == 204
    finally:
        settings.auth_mode = original_mode
        settings.jwt_secret = original_secret


@pytest.mark.asyncio
async def test_viewer_cannot_manage_members(client: AsyncClient) -> None:
    original_mode = settings.auth_mode
    original_secret = settings.jwt_secret
    settings.auth_mode = "jwt"
    settings.jwt_secret = JWT_SECRET
    try:
        async with SessionLocal() as db:
            fleet = Fleet(name="Viewer Members")
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

        headers = {"Authorization": f"Bearer {mint_test_token()}"}
        denied = await client.post(
            "/fleet/members",
            headers=headers,
            json={"user_id": OTHER_USER, "role": "inspector"},
        )
        assert denied.status_code == 403
    finally:
        settings.auth_mode = original_mode
        settings.jwt_secret = original_secret


@pytest.mark.asyncio
async def test_multi_fleet_requires_explicit_fleet_header(client: AsyncClient) -> None:
    original_mode = settings.auth_mode
    original_secret = settings.jwt_secret
    settings.auth_mode = "jwt"
    settings.jwt_secret = JWT_SECRET
    try:
        async with SessionLocal() as db:
            fleet_a = Fleet(name="Fleet A")
            fleet_b = Fleet(name="Fleet B")
            db.add_all([fleet_a, fleet_b])
            await db.flush()
            db.add_all(
                [
                    FleetMembership(
                        fleet_id=fleet_a.id,
                        user_id=TEST_USER_ID,
                        role=FleetRole.ADMIN.value,
                    ),
                    FleetMembership(
                        fleet_id=fleet_b.id,
                        user_id=TEST_USER_ID,
                        role=FleetRole.VIEWER.value,
                    ),
                ]
            )
            await db.commit()
            fleet_a_id, fleet_b_id = fleet_a.id, fleet_b.id

        token = mint_test_token()
        auth = {"Authorization": f"Bearer {token}"}

        # Ambiguous without a fleet header.
        ambiguous = await client.get("/auth/me", headers=auth)
        assert ambiguous.status_code == 409

        # Explicit fleet resolves the role for that fleet.
        scoped = await client.get(
            "/auth/me", headers={**auth, "X-Fleet-ID": fleet_b_id}
        )
        assert scoped.status_code == 200
        assert scoped.json()["fleet_id"] == fleet_b_id
        assert scoped.json()["role"] == "viewer"

        # A fleet the user does not belong to is rejected.
        foreign = await client.get(
            "/auth/me",
            headers={**auth, "X-Fleet-ID": "99999999-9999-9999-9999-999999999999"},
        )
        assert foreign.status_code == 403

        assert fleet_a_id != fleet_b_id
    finally:
        settings.auth_mode = original_mode
        settings.jwt_secret = original_secret
