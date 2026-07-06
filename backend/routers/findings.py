from datetime import datetime, timezone
from uuid import UUID

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from domain import FindingStatus, FleetRole, Severity
from models.db_models import Finding, Inspection, Truck
from models.schemas import FindingOut, FindingUpdate
from security import Principal, require_api_access, require_roles

router = APIRouter(prefix="/findings", tags=["findings"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[FindingOut])
async def list_findings(
    severity: Severity | None = None,
    status: FindingStatus | None = None,
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_api_access),
):
    stmt = select(Finding)
    if principal.fleet_id is not None:
        stmt = (
            stmt.join(Inspection, Inspection.id == Finding.inspection_id)
            .join(Truck, Truck.id == Inspection.truck_id)
            .where(Truck.fleet_id == principal.fleet_id)
        )
    if severity:
        stmt = stmt.where(Finding.severity == severity.value)
    if status:
        stmt = stmt.where(Finding.status == status.value)
    result = await db.execute(stmt.order_by(Finding.id.asc()).limit(limit))
    return result.scalars().all()


@router.patch("/{finding_id}", response_model=FindingOut)
async def update_finding(
    finding_id: UUID,
    payload: FindingUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_roles(FleetRole.INSPECTOR, FleetRole.ADMIN)),
):
    statement = select(Finding).where(Finding.id == str(finding_id))
    if principal.fleet_id is not None:
        statement = (
            statement.join(Inspection, Inspection.id == Finding.inspection_id)
            .join(Truck, Truck.id == Inspection.truck_id)
            .where(Truck.fleet_id == principal.fleet_id)
        )
    finding = (await db.execute(statement)).scalar_one_or_none()
    if finding is None:
        raise HTTPException(404, "Finding not found")

    finding.status = payload.status.value
    finding.resolution_notes = payload.resolution_notes
    if payload.status in (FindingStatus.RESOLVED, FindingStatus.FALSE_POSITIVE):
        finding.resolved_at = datetime.now(timezone.utc)
        finding.resolved_by = principal.user_id
    else:
        finding.resolved_at = None
        finding.resolved_by = None
    await db.commit()
    await db.refresh(finding)
    logger.info(
        "finding.updated",
        extra={
            "request_id": getattr(request.state, "request_id", None),
            "actor": principal.user_id,
            "finding_id": finding.id,
            "status": finding.status,
        },
    )
    return finding
