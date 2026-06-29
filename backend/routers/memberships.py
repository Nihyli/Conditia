from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from domain import FleetRole
from models.db_models import FleetMembership
from models.schemas import FleetMemberCreate, FleetMemberOut, FleetMemberUpdate
from security import Principal, require_api_access, require_roles

router = APIRouter(prefix="/fleet/members", tags=["fleet-members"])


def _scoped_membership_query(principal: Principal):
    stmt = select(FleetMembership)
    if principal.fleet_id is not None:
        stmt = stmt.where(FleetMembership.fleet_id == principal.fleet_id)
    return stmt.order_by(FleetMembership.user_id.asc())


@router.get("", response_model=list[FleetMemberOut])
async def list_members(
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_api_access),
):
    result = await db.execute(_scoped_membership_query(principal))
    return result.scalars().all()


@router.post("", response_model=FleetMemberOut, status_code=201)
async def add_member(
    payload: FleetMemberCreate,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_roles(FleetRole.ADMIN)),
):
    fleet_id = principal.fleet_id
    if fleet_id is None:
        raise HTTPException(400, "Fleet scope is required to add members")
    user_id = str(payload.user_id)
    membership = FleetMembership(
        fleet_id=fleet_id,
        user_id=user_id,
        role=payload.role.value,
    )
    db.add(membership)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "This user is already a fleet member") from exc
    await db.refresh(membership)
    return membership


@router.patch("/{user_id}", response_model=FleetMemberOut)
async def update_member(
    user_id: UUID,
    payload: FleetMemberUpdate,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_roles(FleetRole.ADMIN)),
):
    stmt = select(FleetMembership).where(FleetMembership.user_id == str(user_id))
    if principal.fleet_id is not None:
        stmt = stmt.where(FleetMembership.fleet_id == principal.fleet_id)
    membership = (await db.execute(stmt)).scalar_one_or_none()
    if membership is None:
        raise HTTPException(404, "Fleet member not found")

    if (
        membership.role == FleetRole.ADMIN.value
        and payload.role != FleetRole.ADMIN
        and principal.user_id == membership.user_id
    ):
        admin_count = await db.scalar(
            select(func.count())
            .select_from(FleetMembership)
            .where(
                FleetMembership.fleet_id == membership.fleet_id,
                FleetMembership.role == FleetRole.ADMIN.value,
            )
        )
        if admin_count == 1:
            raise HTTPException(
                409, "Cannot demote the only admin — promote another admin first"
            )

    membership.role = payload.role.value
    await db.commit()
    await db.refresh(membership)
    return membership


@router.delete("/{user_id}", status_code=204)
async def remove_member(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_roles(FleetRole.ADMIN)),
):
    stmt = select(FleetMembership).where(FleetMembership.user_id == str(user_id))
    if principal.fleet_id is not None:
        stmt = stmt.where(FleetMembership.fleet_id == principal.fleet_id)
    membership = (await db.execute(stmt)).scalar_one_or_none()
    if membership is None:
        raise HTTPException(404, "Fleet member not found")

    if membership.role == FleetRole.ADMIN.value:
        admin_count = await db.scalar(
            select(func.count())
            .select_from(FleetMembership)
            .where(
                FleetMembership.fleet_id == membership.fleet_id,
                FleetMembership.role == FleetRole.ADMIN.value,
            )
        )
        if admin_count == 1:
            raise HTTPException(
                409, "Cannot remove the only admin — promote another admin first"
            )

    await db.delete(membership)
    await db.commit()
