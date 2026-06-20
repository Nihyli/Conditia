"""Helpers for change-detection display on the dashboard."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.db_models import Inspection


async def inspections_since_first_seen(
    db: AsyncSession,
    truck_id: str,
    current_inspection_id: str,
    first_seen_inspection_id: str | None,
) -> int:
    """Return how many inspections ago this finding was first detected.

    0 means new this inspection. 3 means first seen three inspections before
    the current one on this truck.
    """
    if (
        first_seen_inspection_id is None
        or first_seen_inspection_id == current_inspection_id
    ):
        return 0

    result = await db.execute(
        select(Inspection.id)
        .where(Inspection.truck_id == truck_id)
        .order_by(Inspection.started_at.asc())
    )
    ordered_ids = list(result.scalars().all())

    if (
        first_seen_inspection_id not in ordered_ids
        or current_inspection_id not in ordered_ids
    ):
        return 0

    first_idx = ordered_ids.index(first_seen_inspection_id)
    current_idx = ordered_ids.index(current_inspection_id)
    return max(0, current_idx - first_idx)
