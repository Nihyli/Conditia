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
    current_started_at = (
        select(Inspection.started_at)
        .where(Inspection.id == current_inspection_id)
        .scalar_subquery()
    )
    # An unlocalized label is not a stable defect identity. Treat it as new
    # rather than attributing unrelated damage to the same historical event.
    if zone is None:
        return current_inspection_id

    result = await db.execute(
        select(Inspection.id)
        .join(Finding, Finding.inspection_id == Inspection.id)
        .where(
            Inspection.truck_id == truck_id,
            Inspection.started_at < current_started_at,
            Inspection.status.in_(("complete", "review_required")),
            Finding.finding_type == finding_type,
            Finding.zone == zone,
        )
        .order_by(Inspection.started_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none() or current_inspection_id
