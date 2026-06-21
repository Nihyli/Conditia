from datetime import datetime, timedelta, timezone

import pytest

from database import SessionLocal
from models.db_models import Finding, Inspection, Truck
from services.change_detection import find_first_occurrence


@pytest.mark.asyncio
async def test_change_matching_requires_a_localized_zone() -> None:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        truck = Truck(vin="1FUJGLDR0CSBT0041")
        db.add(truck)
        await db.flush()
        previous = Inspection(
            truck_id=truck.id,
            started_at=now - timedelta(days=1),
            status="complete",
        )
        current = Inspection(
            truck_id=truck.id,
            started_at=now,
            status="processing",
        )
        db.add_all((previous, current))
        await db.flush()
        db.add(
            Finding(
                inspection_id=previous.id,
                finding_type="dent",
                severity="medium",
                confidence=0.8,
                zone="front",
            )
        )
        await db.commit()

        localized = await find_first_occurrence(
            db,
            truck.id,
            "dent",
            "front",
            current.id,
        )
        unlocalized = await find_first_occurrence(
            db,
            truck.id,
            "dent",
            None,
            current.id,
        )

    assert localized == previous.id
    assert unlocalized == current.id
