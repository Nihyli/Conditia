from fastapi import APIRouter, Depends

from config import settings
from models.schemas import AuthSessionOut
from security import Principal, require_api_access

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=AuthSessionOut)
async def current_session(
    principal: Principal = Depends(require_api_access),
) -> AuthSessionOut:
    return AuthSessionOut(
        auth_mode=settings.auth_mode,
        user_id=principal.user_id,
        fleet_id=principal.fleet_id,
        role=principal.role.value if principal.role else None,
    )
