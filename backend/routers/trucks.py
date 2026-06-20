from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.db_models import Inspection, Truck
from models.schemas import InspectionOut, TruckCreate, TruckOut

router = APIRouter(prefix="/trucks", tags=["trucks"])


@router.post("", response_model=TruckOut, status_code=201)
async def create_truck(payload: TruckCreate, db: AsyncSession = Depends(get_db)):
    truck = Truck(**payload.model_dump())
    db.add(truck)
    await db.commit()
    await db.refresh(truck)
    return truck


@router.get("", response_model=list[TruckOut])
async def list_trucks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Truck).order_by(Truck.created_at.desc()))
    return result.scalars().all()


@router.get("/{truck_id}", response_model=TruckOut)
async def get_truck(truck_id: str, db: AsyncSession = Depends(get_db)):
    truck = await db.get(Truck, truck_id)
    if truck is None:
        raise HTTPException(404, "Truck not found")
    return truck


@router.get("/{truck_id}/inspections", response_model=list[InspectionOut])
async def truck_inspections(truck_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Inspection)
        .where(Inspection.truck_id == truck_id)
        .order_by(Inspection.started_at.desc())
    )
    return result.scalars().all()
