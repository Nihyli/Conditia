"""Authorized delivery for private inspection media."""

import mimetypes
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.db_models import Inspection, InspectionMedia, Truck
from security import Principal, require_api_access
from services.storage import LocalStorageService, StorageError, storage_service

router = APIRouter(prefix="/inspection-media", tags=["inspection-media"])


@router.get("/{media_id}/content")
async def get_media_content(
    media_id: UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_api_access),
):
    statement = select(InspectionMedia).where(InspectionMedia.id == str(media_id))
    if principal.fleet_id is not None:
        statement = (
            statement.join(Inspection, Inspection.id == InspectionMedia.inspection_id)
            .join(Truck, Truck.id == Inspection.truck_id)
            .where(Truck.fleet_id == principal.fleet_id)
        )
    media = (await db.execute(statement)).scalar_one_or_none()
    if media is None:
        raise HTTPException(404, "Media not found")

    content_type = mimetypes.guess_type(media.storage_path)[0] or "application/octet-stream"
    try:
        signed_url = await storage_service.delivery_url(media.storage_path)
        if signed_url is not None:
            return RedirectResponse(
                signed_url,
                status_code=307,
                headers={"Cache-Control": "private, no-store"},
            )
        if isinstance(storage_service, LocalStorageService):
            return FileResponse(
                storage_service.local_path(media.storage_path),
                media_type=content_type,
                headers={
                    "Cache-Control": "private, no-store",
                    "Content-Disposition": "inline",
                },
            )
    except StorageError as exc:
        raise HTTPException(503, "Media is temporarily unavailable") from exc
    raise HTTPException(503, "Media delivery is not configured")
