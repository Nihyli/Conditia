from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.db_models import Inspection, Report, Truck
from models.schemas import ReportOut
from security import Principal, require_api_access

router = APIRouter(prefix="/reports", tags=["reports"])


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
    return result.scalars().all()


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
    return report
