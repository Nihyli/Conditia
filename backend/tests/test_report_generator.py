import pytest

from database import SessionLocal
from models.db_models import Inspection, Truck
from services.report_generator import generate


@pytest.mark.asyncio
async def test_review_required_report_never_claims_clear() -> None:
    async with SessionLocal() as db:
        truck = Truck(vin="1FUJGLDR0CSBT0041")
        db.add(truck)
        await db.flush()
        inspection = Inspection(truck_id=truck.id, status="processing")
        db.add(inspection)
        await db.flush()

        report = await generate(
            db,
            inspection.id,
            requires_human_review=True,
        )
        await db.commit()

        assert "No clear result" in report.summary
        assert report.raw_json["requires_human_review"] is True
