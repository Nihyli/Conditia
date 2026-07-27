import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from domain import FleetRole
from models.db_models import FleetMembership
from models.schemas import FleetMemberCreate, FleetMemberOut, FleetMemberUpdate
from security import Principal, require_api_access, require_roles

router = APIRouter(prefix="/fleet/members", tags=["fleet-members"])
logger = logging.getLogger(__name__)


def _require_fleet(principal: Principal) -> str:
    if principal.fleet_id is None:
        raise HTTPException(400, "Fleet scope is required to manage members")
    return principal.fleet_id


@router.get("", response_model=list[FleetMemberOut])
async def list_members(
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_api_access),
):
    fleet_id = _require_fleet(principal)
    result = await db.execute(
        select(FleetMembership)
        .where(FleetMembership.fleet_id == fleet_id)
        .order_by(FleetMembership.user_id.asc())
    )
    return result.scalars().all()


@router.post("", response_model=FleetMemberOut, status_code=201)
async def add_member(
    payload: FleetMemberCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_roles(FleetRole.ADMIN)),
):
    fleet_id = _require_fleet(principal)
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
    logger.info(
        "membership.added",
        extra={
            "request_id": getattr(request.state, "request_id", None),
            "actor": principal.user_id,
            "fleet_id": fleet_id,
            "target_user_id": user_id,
            "role": payload.role.value,
        },
    )
    return membership


@router.patch("/{user_id}", response_model=FleetMemberOut)
async def update_member(
    user_id: UUID,
    payload: FleetMemberUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_roles(FleetRole.ADMIN)),
):
    fleet_id = _require_fleet(principal)
    membership = await db.get(FleetMembership, (fleet_id, str(user_id)))
    if membership is None:
        raise HTTPException(404, "Fleet member not found")

    previous_role = membership.role

    if (
        membership.role == FleetRole.ADMIN.value
        and payload.role != FleetRole.ADMIN
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
    logger.info(
        "membership.role_changed",
        extra={
            "request_id": getattr(request.state, "request_id", None),
            "actor": principal.user_id,
            "fleet_id": fleet_id,
            "target_user_id": str(user_id),
            "previous_role": previous_role,
            "new_role": payload.role.value,
        },
    )
    return membership


@router.delete("/{user_id}", status_code=204)
async def remove_member(
    user_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_roles(FleetRole.ADMIN)),
):
    fleet_id = _require_fleet(principal)
    membership = await db.get(FleetMembership, (fleet_id, str(user_id)))
    if membership is None:
        raise HTTPException(404, "Fleet member not found")

    removed_role = membership.role

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
    logger.info(
        "membership.removed",
        extra={
            "request_id": getattr(request.state, "request_id", None),
            "actor": principal.user_id,
            "fleet_id": fleet_id,
            "target_user_id": str(user_id),
            "removed_role": removed_role,
        },
    )
