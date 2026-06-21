"""Batched inspection read-model assembly."""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.db_models import Finding, Inspection, InspectionMedia, Truck
from models.schemas import FindingOut, InspectionSummary, MediaOut
from utils import worst_severity


async def build_inspection_summaries(
    db: AsyncSession,
    inspections: list[Inspection],
) -> list[InspectionSummary]:
    if not inspections:
        return []

    inspection_ids = [inspection.id for inspection in inspections]
    truck_ids = {inspection.truck_id for inspection in inspections}

    truck_result = await db.execute(select(Truck).where(Truck.id.in_(truck_ids)))
    trucks = {truck.id: truck for truck in truck_result.scalars().all()}

    finding_result = await db.execute(
        select(Finding).where(Finding.inspection_id.in_(inspection_ids))
    )
    findings_by_inspection: dict[str, list[Finding]] = defaultdict(list)
    for finding in finding_result.scalars().all():
        findings_by_inspection[finding.inspection_id].append(finding)

    media_result = await db.execute(
        select(InspectionMedia)
        .where(InspectionMedia.inspection_id.in_(inspection_ids))
        .order_by(InspectionMedia.captured_at.asc())
    )
    media_by_inspection: dict[str, list[InspectionMedia]] = defaultdict(list)
    for media in media_result.scalars().all():
        media_by_inspection[media.inspection_id].append(media)

    history_result = await db.execute(
        select(Inspection.truck_id, Inspection.id)
        .where(Inspection.truck_id.in_(truck_ids))
        .order_by(Inspection.truck_id.asc(), Inspection.started_at.asc())
    )
    ordered_by_truck: dict[str, list[str]] = defaultdict(list)
    for truck_id, inspection_id in history_result.all():
        ordered_by_truck[truck_id].append(inspection_id)
    positions_by_truck = {
        truck_id: {
            inspection_id: position
            for position, inspection_id in enumerate(ordered_ids)
        }
        for truck_id, ordered_ids in ordered_by_truck.items()
    }

    summaries: list[InspectionSummary] = []
    for inspection in inspections:
        truck = trucks.get(inspection.truck_id)
        findings = findings_by_inspection[inspection.id]
        positions = positions_by_truck.get(inspection.truck_id, {})
        current_position = positions.get(inspection.id, 0)
        finding_outputs: list[FindingOut] = []
        for finding in findings:
            first_position = positions.get(
                finding.first_seen_inspection_id,
                current_position,
            )
            base = FindingOut.model_validate(finding)
            finding_outputs.append(
                base.model_copy(
                    update={
                        "first_detected_inspections_ago": max(
                            0,
                            current_position - first_position,
                        )
                    }
                )
            )

        summaries.append(
            InspectionSummary(
                id=inspection.id,
                truck_id=inspection.truck_id,
                truck_label=(truck.license_plate or truck.vin)
                if truck
                else "Unknown truck",
                make=truck.make if truck else None,
                model=truck.model if truck else None,
                started_at=inspection.started_at,
                status=inspection.status,
                capture_source=inspection.capture_source,
                finding_count=len(finding_outputs),
                worst_severity=worst_severity(
                    [finding.severity for finding in findings]
                ),
                findings=finding_outputs,
                media=[
                    MediaOut.model_validate(media)
                    for media in media_by_inspection[inspection.id]
                ],
            )
        )
    return summaries
