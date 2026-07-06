"""Authorized delivery for private inspection media."""

import mimetypes
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.db_models import Inspection, InspectionMedia, Truck
from security import Principal, require_api_access
from services.media_tokens import (
    media_content_path,
    mint_media_access_token,
    verify_media_access_token,
)
from services.storage import LocalStorageService, StorageError, storage_service

router = APIRouter(prefix="/inspection-media", tags=["inspection-media"])
# Content delivery is mounted without the global API auth dependency so browsers
# can load media via short-lived signed query tokens.
public_router = APIRouter(prefix="/inspection-media", tags=["inspection-media"])


async def _authorized_media(
    db: AsyncSession,
    media_id: UUID,
    principal: Principal | None,
    access_token: str | None,
) -> InspectionMedia:
    if access_token is not None:
        if not verify_media_access_token(str(media_id), access_token):
            raise HTTPException(401, "Invalid or expired media access token")
        statement = select(InspectionMedia).where(InspectionMedia.id == str(media_id))
        media = (await db.execute(statement)).scalar_one_or_none()
        if media is None:
            raise HTTPException(404, "Media not found")
        return media

    if principal is None:
        raise HTTPException(401, "Sign in required")

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
    return media


async def _deliver_media(media: InspectionMedia):
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


@router.get("/{media_id}/access")
async def get_media_access(
    media_id: UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_api_access),
):
    """Mint a short-lived URL browsers can load in <img> without Authorization."""
    await _authorized_media(db, media_id, principal, None)
    token, expires_at = mint_media_access_token(
        str(media_id),
        fleet_id=principal.fleet_id,
        user_id=principal.user_id,
    )
    return {
        "url": media_content_path(media_id, token),
        "expires_at": expires_at,
    }


@public_router.get("/{media_id}/content")
async def get_media_content(
    media_id: UUID,
    access_token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    x_fleet_id: str | None = Header(default=None, alias="X-Fleet-ID"),
):
    if access_token is not None:
        media = await _authorized_media(db, media_id, None, access_token)
    else:
        principal = await require_api_access(
            db, authorization, x_api_key, x_fleet_id
        )
        media = await _authorized_media(db, media_id, principal, None)
    return await _deliver_media(media)
