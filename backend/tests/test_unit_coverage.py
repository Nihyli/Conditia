"""Targeted unit tests for remaining uncovered branches."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from httpx import AsyncClient

from domain import FleetRole
from models.schemas import TruckCreate
from security import Principal, _normalize_fleet_id


def test_truck_create_whitespace_make_normalizes_to_none() -> None:
    truck = TruckCreate(vin="1FUJGLDR0CSBT0041", make="   ")
    assert truck.make is None


def test_truck_create_whitespace_model_normalizes_to_none() -> None:
    truck = TruckCreate(vin="1FUJGLDR0CSBT0041", model="  \t ")
    assert truck.model is None


def test_truck_create_whitespace_license_plate_normalizes_to_none() -> None:
    truck = TruckCreate(vin="1FUJGLDR0CSBT0041", license_plate="   ")
    assert truck.license_plate is None


def test_principal_is_service_true() -> None:
    p = Principal(user_id=None, fleet_id=None, role=FleetRole.ADMIN)
    assert p.is_service is True


def test_principal_is_service_false_with_user() -> None:
    p = Principal(user_id="uid", fleet_id=None, role=FleetRole.ADMIN)
    assert p.is_service is False


def test_principal_is_service_false_with_non_admin_role() -> None:
    p = Principal(user_id=None, fleet_id=None, role=FleetRole.VIEWER)
    assert p.is_service is False


def test_normalize_fleet_id_none() -> None:
    assert _normalize_fleet_id(None) is None


def test_normalize_fleet_id_empty_string() -> None:
    assert _normalize_fleet_id("   ") is None


def test_normalize_fleet_id_invalid_uuid() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _normalize_fleet_id("not-a-uuid")
    assert exc_info.value.status_code == 400


def test_normalize_fleet_id_valid_uuid() -> None:
    result = _normalize_fleet_id("00000000-0000-0000-0000-000000000001")
    assert result == "00000000-0000-0000-0000-000000000001"


@pytest.mark.asyncio
async def test_auth_me_disabled_mode(client: AsyncClient) -> None:
    response = await client.get("/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["auth_mode"] == "disabled"
    assert data["role"] == "admin"
    assert data["available_fleets"] == []
