from fastapi import APIRouter, Depends, HTTPException, Query

from auth.dependencies import require_role
from auth.roles import UserRole
from config import settings
from models.schemas import DataStatusOut, SeedResultOut, UnseedResultOut
from seed import data_status, seed_demo, unseed

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin_flag() -> None:
    if not settings.admin_enabled:
        raise HTTPException(
            status_code=403,
            detail="Admin endpoints are disabled. Set ADMIN_ENABLED=true to enable.",
        )


@router.get("/data-status", response_model=DataStatusOut)
async def get_data_status(_: object = Depends(require_role(UserRole.ADMIN))):
    _require_admin_flag()
    return await data_status()


@router.post("/seed", response_model=SeedResultOut)
async def post_seed(
    force: bool = Query(
        False,
        description="Clear existing data before seeding demo fleet",
    ),
    _: object = Depends(require_role(UserRole.ADMIN)),
):
    _require_admin_flag()
    return await seed_demo(force=force)


@router.post("/unseed", response_model=UnseedResultOut)
async def post_unseed(
    clear_storage: bool = Query(
        True,
        description="Also delete uploaded media files from disk",
    ),
    _: object = Depends(require_role(UserRole.ADMIN)),
):
    _require_admin_flag()
    return await unseed(clear_storage=clear_storage)