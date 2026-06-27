from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.db_models import Fleet, Inspection, Truck
from models.schemas import InspectionOut, TruckCreate, TruckOut
from security import Principal, require_api_access

router = APIRouter(prefix="/trucks", tags=["trucks"])


@router.post("", response_model=TruckOut, status_code=201)
async def create_truck(
    payload: TruckCreate,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_api_access),
):
    values = payload.model_dump(mode="json")
    if principal.fleet_id is not None:
        if values["fleet_id"] not in (None, principal.fleet_id):
            raise HTTPException(403, "Fleet access denied")
        values["fleet_id"] = principal.fleet_id
    if values["fleet_id"] is not None and await db.get(Fleet, values["fleet_id"]) is None:
        raise HTTPException(404, "Fleet not found")
    truck = Truck(**values)
    db.add(truck)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "A truck with this VIN already exists") from exc
    await db.refresh(truck)
    return truck


@router.get("", response_model=list[TruckOut])
async def list_trucks(
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_api_access),
):
    statement = select(Truck)
    if principal.fleet_id is not None:
        statement = statement.where(Truck.fleet_id == principal.fleet_id)
    result = await db.execute(statement.order_by(Truck.created_at.desc()).limit(limit))
    return result.scalars().all()


@router.get("/{truck_id}", response_model=TruckOut)
async def get_truck(
    truck_id: UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_api_access),
):
    statement = select(Truck).where(Truck.id == str(truck_id))
    if principal.fleet_id is not None:
        statement = statement.where(Truck.fleet_id == principal.fleet_id)
    truck = (await db.execute(statement)).scalar_one_or_none()
    if truck is None:
        raise HTTPException(404, "Truck not found")
    return truck


@router.get("/{truck_id}/inspections", response_model=list[InspectionOut])
async def truck_inspections(
    truck_id: UUID,
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_api_access),
):
    truck_key = str(truck_id)
    truck_statement = select(Truck.id).where(Truck.id == truck_key)
    if principal.fleet_id is not None:
        truck_statement = truck_statement.where(Truck.fleet_id == principal.fleet_id)
    if (await db.execute(truck_statement)).scalar_one_or_none() is None:
        raise HTTPException(404, "Truck not found")
    result = await db.execute(
        select(Inspection)
        .where(Inspection.truck_id == truck_key)
        .order_by(Inspection.started_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
