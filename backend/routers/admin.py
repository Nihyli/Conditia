from fastapi import APIRouter, HTTPException, Query

from config import settings
from models.schemas import DataStatusOut, SeedResultOut, UnseedResultOut
from seed import data_status, seed_demo, unseed

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin() -> None:
    if not settings.admin_enabled:
        raise HTTPException(
            status_code=403,
            detail="Admin endpoints are disabled. Set ADMIN_ENABLED=true to enable.",
        )


@router.get("/data-status", response_model=DataStatusOut)
async def get_data_status():
    _require_admin()
    return await data_status()


@router.post("/seed", response_model=SeedResultOut)
async def post_seed(
    force: bool = Query(
        False,
        description="Clear existing data before seeding demo fleet",
    ),
):
    _require_admin()
    return await seed_demo(force=force)


@router.post("/unseed", response_model=UnseedResultOut)
async def post_unseed(
    clear_storage: bool = Query(
        True,
        description="Also delete uploaded media files from disk",
    ),
):
    _require_admin()
    return await unseed(clear_storage=clear_storage)
