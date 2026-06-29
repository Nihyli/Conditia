"""Inspection capture coverage rules for mobile walk-arounds."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain import CaptureAngle
from models.db_models import InspectionMedia

REQUIRED_CAPTURE_ANGLES: tuple[CaptureAngle, ...] = (
    CaptureAngle.FRONT,
    CaptureAngle.REAR,
    CaptureAngle.DRIVER_SIDE,
    CaptureAngle.PASSENGER_SIDE,
)

OPTIONAL_CAPTURE_ANGLES: tuple[CaptureAngle, ...] = (
    CaptureAngle.TOP,
    CaptureAngle.UNDERCARRIAGE,
)


async def missing_required_angles(
    db: AsyncSession, inspection_id: str
) -> list[str]:
    result = await db.execute(
        select(InspectionMedia.capture_angle).where(
            InspectionMedia.inspection_id == inspection_id,
            InspectionMedia.capture_angle.is_not(None),
        )
    )
    present: set[CaptureAngle] = set()
    for raw in result.scalars().all():
        if not raw:
            continue
        try:
            present.add(CaptureAngle(raw))
        except ValueError:
            continue
    return [angle.value for angle in REQUIRED_CAPTURE_ANGLES if angle not in present]
