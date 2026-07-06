from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from models.db_models import FleetMembership
from models.schemas import AuthFleetOut, AuthSessionOut
from security import Principal, require_api_access

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=AuthSessionOut)
async def current_session(
    principal: Principal = Depends(require_api_access),
    db: AsyncSession = Depends(get_db),
) -> AuthSessionOut:
    fleets: list[AuthFleetOut] = []
    if principal.user_id is not None:
        result = await db.execute(
            select(FleetMembership)
            .where(FleetMembership.user_id == principal.user_id)
            .order_by(FleetMembership.fleet_id.asc())
        )
        fleets = [
            AuthFleetOut(fleet_id=row.fleet_id, role=row.role)
            for row in result.scalars().all()
        ]
    return AuthSessionOut(
        auth_mode=settings.auth_mode,
        user_id=principal.user_id,
        fleet_id=principal.fleet_id,
        role=principal.role.value if principal.role else None,
        available_fleets=fleets,
    )
