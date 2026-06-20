"""Change detection -- the feature that turns a photo tool into an intelligence
platform. It answers not just "is this damaged" but "when did this first appear."

For the MVP we match findings across a truck's prior inspections by
(finding_type, zone). A production version tightens this with bounding-box
location signatures and tolerance (see the technical writeup).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.db_models import Finding, Inspection


async def find_first_occurrence(
    db: AsyncSession,
    truck_id: str,
    finding_type: str,
    zone: str | None,
    current_inspection_id: str,
) -> str:
    """Walk this truck's inspections oldest-first; return the inspection id where
    this finding (same type + zone) was first seen. Defaults to the current
    inspection if it has never been seen before (i.e. it is new).
    """
    result = await db.execute(
        select(Inspection)
        .where(Inspection.truck_id == truck_id)
        .where(Inspection.id != current_inspection_id)
        .order_by(Inspection.started_at.asc())
    )
    previous = result.scalars().all()

    first_seen = current_inspection_id
    for inspection in previous:
        match = await db.execute(
            select(Finding.id)
            .where(Finding.inspection_id == inspection.id)
            .where(Finding.finding_type == finding_type)
            .where(Finding.zone == zone)
            .limit(1)
        )
        if match.scalar_one_or_none() is not None:
            first_seen = inspection.id
            break

    return first_seen
