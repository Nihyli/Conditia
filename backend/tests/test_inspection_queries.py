from datetime import datetime, timedelta, timezone

import pytest

from database import SessionLocal
from models.db_models import Finding, Inspection, InspectionMedia, Truck
from services.inspection_queries import build_inspection_summaries


@pytest.mark.asyncio
async def test_summary_assembles_history_findings_media_and_truck_label() -> None:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        truck = Truck(
            vin="1FUJGLDR0CSBT0041",
            license_plate="TRK-001",
            make="Volvo",
            model="VNL",
        )
        db.add(truck)
        await db.flush()
        first = Inspection(
            truck_id=truck.id,
            started_at=now - timedelta(days=2),
            status="complete",
        )
        middle = Inspection(
            truck_id=truck.id,
            started_at=now - timedelta(days=1),
            status="complete",
        )
        current = Inspection(
            truck_id=truck.id,
            started_at=now,
            status="complete",
        )
        db.add_all((first, middle, current))
        await db.flush()
        media = InspectionMedia(
            inspection_id=current.id,
            media_type="photo",
            capture_angle="front",
            capture_source="mobile",
            storage_path=f"{current.id}/front/image.png",
        )
        db.add(media)
        await db.flush()
        db.add_all(
            (
                Finding(
                    inspection_id=current.id,
                    media_id=media.id,
                    title="Old dent",
                    finding_type="dent",
                    severity="critical",
                    confidence=0.9,
                    status="open",
                    zone="front",
                    first_seen_inspection_id=first.id,
                ),
                Finding(
                    inspection_id=current.id,
                    title="New scratch",
                    finding_type="scratch",
                    severity="low",
                    confidence=0.7,
                    status="open",
                    zone="rear",
                ),
            )
        )
        await db.commit()

        summaries = await build_inspection_summaries(db, [current])

    summary = summaries[0]
    assert summary.truck_label == "TRK-001"
    assert summary.make == "Volvo"
    assert summary.finding_count == 2
    assert summary.worst_severity == "critical"
    assert summary.media[0].id == media.id
    age_by_title = {
        finding.title: finding.first_detected_inspections_ago
        for finding in summary.findings
    }
    assert age_by_title == {"Old dent": 2, "New scratch": 0}


@pytest.mark.asyncio
async def test_summary_handles_missing_truck_defensively() -> None:
    # The function may be used with detached/read-replica data. Preserve a
    # stable label even if the associated truck was not returned.
    orphan = Inspection(
        id="00000000-0000-0000-0000-000000000001",
        truck_id="00000000-0000-0000-0000-000000000002",
        started_at=datetime.now(timezone.utc),
        status="complete",
        capture_source="mobile",
    )
    async with SessionLocal() as db:
        summaries = await build_inspection_summaries(db, [orphan])

    assert summaries[0].truck_label == "Unknown truck"
    assert summaries[0].findings == []
    assert summaries[0].media == []
