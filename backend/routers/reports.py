from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.db_models import Finding, Inspection, Report, Truck
from models.schemas import ReportOut
from security import Principal, require_api_access

router = APIRouter(prefix="/reports", tags=["reports"])


async def _annotate_staleness(db: AsyncSession, report: Report) -> ReportOut:
    """Compare live finding counts against the snapshot to detect staleness."""
    out = ReportOut.model_validate(report)
    live_total = await db.scalar(
        select(func.count())
        .select_from(Finding)
        .where(Finding.inspection_id == report.inspection_id)
    )
    out.findings_changed = (live_total or 0) != report.total_findings
    return out


@router.get("", response_model=list[ReportOut])
async def list_reports(
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_api_access),
):
    statement = select(Report)
    if principal.fleet_id is not None:
        statement = (
            statement.join(Inspection, Inspection.id == Report.inspection_id)
            .join(Truck, Truck.id == Inspection.truck_id)
            .where(Truck.fleet_id == principal.fleet_id)
        )
    result = await db.execute(
        statement.order_by(Report.generated_at.desc()).limit(limit)
    )
    return [
        await _annotate_staleness(db, report)
        for report in result.scalars().all()
    ]


@router.get("/{inspection_id}", response_model=ReportOut)
async def get_report(
    inspection_id: UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_api_access),
):
    statement = select(Report).where(Report.inspection_id == str(inspection_id))
    if principal.fleet_id is not None:
        statement = (
            statement.join(Inspection, Inspection.id == Report.inspection_id)
            .join(Truck, Truck.id == Inspection.truck_id)
            .where(Truck.fleet_id == principal.fleet_id)
        )
    result = await db.execute(statement)
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(404, "Report not found")
    return await _annotate_staleness(db, report)
