import pytest

from database import SessionLocal
from models.db_models import Finding, Inspection, Report, Truck
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


@pytest.mark.asyncio
async def test_report_summarizes_findings_and_upserts() -> None:
    async with SessionLocal() as db:
        truck = Truck(vin="1FUJGLDR0CSBT0041")
        db.add(truck)
        await db.flush()
        inspection = Inspection(truck_id=truck.id, status="processing")
        db.add(inspection)
        await db.flush()
        db.add_all(
            (
                Finding(
                    inspection_id=inspection.id,
                    title="Dent",
                    finding_type="dent",
                    severity="critical",
                    confidence=0.9,
                    status="open",
                ),
                Finding(
                    inspection_id=inspection.id,
                    title="Scratch",
                    finding_type="scratch",
                    severity="low",
                    confidence=0.7,
                    status="acknowledged",
                ),
            )
        )
        await db.flush()

        report = await generate(db, inspection.id)
        first_id = report.id
        reviewed = await generate(db, inspection.id, requires_human_review=True)
        await db.commit()

        reports = (
            await db.execute(
                Report.__table__.select().where(Report.inspection_id == inspection.id)
            )
        ).all()

    assert reviewed.id == first_id
    assert reviewed.total_findings == 2
    assert reviewed.critical_findings == 1
    assert "Manual review is required" in reviewed.summary
    assert len(reports) == 1
