from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from database import get_db
from models.db_models import Finding, Inspection, Truck
from models.schemas import FleetStatsOut

router = APIRouter(
    prefix="/fleet",
    tags=["fleet"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/stats", response_model=FleetStatsOut)
async def fleet_stats(db: AsyncSession = Depends(get_db)):
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    active_trucks = await db.scalar(select(func.count()).select_from(Truck)) or 0

    inspections_today = (
        await db.scalar(
            select(func.count())
            .select_from(Inspection)
            .where(Inspection.started_at >= today_start)
        )
        or 0
    )

    inspections_pending = (
        await db.scalar(
            select(func.count())
            .select_from(Inspection)
            .where(Inspection.status.in_(("pending", "processing")))
        )
        or 0
    )

    inspections_complete_today = (
        await db.scalar(
            select(func.count())
            .select_from(Inspection)
            .where(
                Inspection.started_at >= today_start,
                Inspection.status == "complete",
            )
        )
        or 0
    )

    open_findings = (
        await db.scalar(select(func.count()).select_from(Finding)) or 0
    )

    return FleetStatsOut(
        active_trucks=active_trucks,
        inspections_today=inspections_today,
        inspections_pending=inspections_pending,
        inspections_complete_today=inspections_complete_today,
        open_findings=open_findings,
    )
