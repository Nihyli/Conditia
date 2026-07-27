"""Tests for services/coverage.py – missing-angles logic."""

from __future__ import annotations

import pytest

from database import SessionLocal
from domain import CaptureAngle
from models.db_models import Inspection, InspectionMedia, Truck
from services.coverage import (
    OPTIONAL_CAPTURE_ANGLES,
    REQUIRED_CAPTURE_ANGLES,
    missing_required_angles,
)


@pytest.mark.asyncio
async def test_no_media_returns_all_required_angles() -> None:
    async with SessionLocal() as db:
        truck = Truck(vin="1FUJGLDR0CSBT0041")
        db.add(truck)
        await db.flush()
        inspection = Inspection(truck_id=truck.id, status="uploading")
        db.add(inspection)
        await db.flush()
        missing = await missing_required_angles(db, inspection.id)
    assert missing == [a.value for a in REQUIRED_CAPTURE_ANGLES]


@pytest.mark.asyncio
async def test_all_required_angles_present_returns_empty() -> None:
    async with SessionLocal() as db:
        truck = Truck(vin="1FUJGLDR0CSBT0041")
        db.add(truck)
        await db.flush()
        inspection = Inspection(truck_id=truck.id, status="uploading")
        db.add(inspection)
        await db.flush()
        for angle in REQUIRED_CAPTURE_ANGLES:
            db.add(
                InspectionMedia(
                    inspection_id=inspection.id,
                    media_type="photo",
                    capture_angle=angle.value,
                    storage_path=f"{inspection.id}/{angle.value}.png",
                )
            )
        await db.flush()
        missing = await missing_required_angles(db, inspection.id)
    assert missing == []


@pytest.mark.asyncio
async def test_partial_angles_returns_only_missing() -> None:
    async with SessionLocal() as db:
        truck = Truck(vin="1FUJGLDR0CSBT0041")
        db.add(truck)
        await db.flush()
        inspection = Inspection(truck_id=truck.id, status="uploading")
        db.add(inspection)
        await db.flush()
        db.add(
            InspectionMedia(
                inspection_id=inspection.id,
                media_type="photo",
                capture_angle=CaptureAngle.FRONT.value,
                storage_path=f"{inspection.id}/front.png",
            )
        )
        db.add(
            InspectionMedia(
                inspection_id=inspection.id,
                media_type="photo",
                capture_angle=CaptureAngle.REAR.value,
                storage_path=f"{inspection.id}/rear.png",
            )
        )
        await db.flush()
        missing = await missing_required_angles(db, inspection.id)
    assert missing == [CaptureAngle.DRIVER_SIDE.value, CaptureAngle.PASSENGER_SIDE.value]


@pytest.mark.asyncio
async def test_optional_angles_do_not_satisfy_required() -> None:
    async with SessionLocal() as db:
        truck = Truck(vin="1FUJGLDR0CSBT0041")
        db.add(truck)
        await db.flush()
        inspection = Inspection(truck_id=truck.id, status="uploading")
        db.add(inspection)
        await db.flush()
        for angle in OPTIONAL_CAPTURE_ANGLES:
            db.add(
                InspectionMedia(
                    inspection_id=inspection.id,
                    media_type="photo",
                    capture_angle=angle.value,
                    storage_path=f"{inspection.id}/{angle.value}.png",
                )
            )
        await db.flush()
        missing = await missing_required_angles(db, inspection.id)
    assert len(missing) == len(REQUIRED_CAPTURE_ANGLES)


@pytest.mark.asyncio
async def test_null_angle_media_is_ignored() -> None:
    async with SessionLocal() as db:
        truck = Truck(vin="1FUJGLDR0CSBT0041")
        db.add(truck)
        await db.flush()
        inspection = Inspection(truck_id=truck.id, status="uploading")
        db.add(inspection)
        await db.flush()
        db.add(
            InspectionMedia(
                inspection_id=inspection.id,
                media_type="photo",
                capture_angle=None,
                storage_path=f"{inspection.id}/unknown.png",
            )
        )
        await db.flush()
        missing = await missing_required_angles(db, inspection.id)
    assert missing == [a.value for a in REQUIRED_CAPTURE_ANGLES]
