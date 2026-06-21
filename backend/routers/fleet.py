from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.db_models import Finding, Inspection, Truck
from models.schemas import FleetStatsOut
from security import Principal, require_api_access

router = APIRouter(prefix="/fleet", tags=["fleet"])


@router.get("/stats", response_model=FleetStatsOut)
async def fleet_stats(
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_api_access),
):
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    active_trucks_statement = select(func.count()).select_from(Truck)
    if principal.fleet_id is not None:
        active_trucks_statement = active_trucks_statement.where(
            Truck.fleet_id == principal.fleet_id
        )
    active_trucks = await db.scalar(active_trucks_statement) or 0

    inspections_today_statement = (
        select(func.count())
        .select_from(Inspection)
        .where(Inspection.started_at >= today_start)
    )
    if principal.fleet_id is not None:
        inspections_today_statement = inspections_today_statement.join(Truck).where(
            Truck.fleet_id == principal.fleet_id
        )
    inspections_today = await db.scalar(inspections_today_statement) or 0

    inspections_pending_statement = (
        select(func.count())
        .select_from(Inspection)
        .where(Inspection.status.in_(("uploading", "submitted", "processing")))
    )
    if principal.fleet_id is not None:
        inspections_pending_statement = inspections_pending_statement.join(Truck).where(
            Truck.fleet_id == principal.fleet_id
        )
    inspections_pending = await db.scalar(inspections_pending_statement) or 0

    inspections_complete_statement = (
        select(func.count())
        .select_from(Inspection)
        .where(
            Inspection.started_at >= today_start,
            Inspection.status == "complete",
        )
    )
    if principal.fleet_id is not None:
        inspections_complete_statement = inspections_complete_statement.join(Truck).where(
            Truck.fleet_id == principal.fleet_id
        )
    inspections_complete_today = await db.scalar(inspections_complete_statement) or 0

    open_findings_statement = (
        select(func.count())
        .select_from(Finding)
        .where(Finding.status.in_(("open", "acknowledged")))
    )
    if principal.fleet_id is not None:
        open_findings_statement = (
            open_findings_statement.join(Inspection)
            .join(Truck)
            .where(Truck.fleet_id == principal.fleet_id)
        )
    open_findings = await db.scalar(open_findings_statement) or 0

    return FleetStatsOut(
        active_trucks=active_trucks,
        inspections_today=inspections_today,
        inspections_pending=inspections_pending,
        inspections_complete_today=inspections_complete_today,
        open_findings=open_findings,
    )
