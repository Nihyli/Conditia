from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from database import get_db
from models.db_models import Finding
from models.schemas import FindingOut

router = APIRouter(
    prefix="/findings",
    tags=["findings"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[FindingOut])
async def list_findings(
    severity: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Finding)
    if severity:
        stmt = stmt.where(Finding.severity == severity)
    result = await db.execute(stmt)
    return result.scalars().all()
