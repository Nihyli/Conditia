"""Who is calling, and what they're allowed to do."""

import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from domain import FleetRole
from models.db_models import FleetMembership
from services.jwt_verify import decode_access_token_subject

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Principal:
    user_id: str | None
    fleet_id: str | None
    role: FleetRole | None

    @property
    def is_service(self) -> bool:
        return self.user_id is None and self.role == FleetRole.ADMIN


def _normalize_fleet_id(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Fleet-ID must be a valid UUID",
        ) from exc


def _decode_bearer_token(token: str) -> str:
    if settings.jwt_secret is None and not settings.supabase_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT auth is not configured",
        )
    try:
        return decode_access_token_subject(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        ) from None


async def _select_membership(
    db: AsyncSession, user_id: str, requested_fleet_id: str | None
) -> FleetMembership:
    """Resolve which fleet a user is acting as.

    One membership: use it. Multiple: require an explicit ``X-Fleet-ID`` so the
    tenant context is never picked arbitrarily.
    """
    result = await db.execute(
        select(FleetMembership)
        .where(FleetMembership.user_id == user_id)
        .order_by(FleetMembership.fleet_id.asc())
    )
    memberships = list(result.scalars().all())
    if not memberships:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No fleet access for this account",
        )
    if requested_fleet_id is not None:
        for membership in memberships:
            if membership.fleet_id == requested_fleet_id:
                return membership
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to the requested fleet",
        )
    if len(memberships) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Multiple fleet memberships — set the X-Fleet-ID header",
        )
    return memberships[0]


async def require_api_access(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    x_fleet_id: str | None = Header(default=None, alias="X-Fleet-ID"),
) -> Principal:
    if settings.auth_mode == "disabled":
        return Principal(user_id=None, fleet_id=None, role=FleetRole.ADMIN)

    if settings.auth_mode == "api_key":
        if settings.api_key is None or x_api_key is None:
            logger.info("auth.api_key_rejected", extra={"reason": "missing"})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        if not secrets.compare_digest(x_api_key, settings.api_key):
            logger.info("auth.api_key_rejected", extra={"reason": "mismatch"})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        fleet_id = str(settings.api_fleet_id) if settings.api_fleet_id else None
        return Principal(user_id=None, fleet_id=fleet_id, role=FleetRole.ADMIN)

    if settings.auth_mode != "jwt":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is misconfigured",
        )

    if authorization is None or not authorization.startswith("Bearer "):
        logger.info("auth.jwt_rejected", extra={"reason": "missing_bearer"})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in required",
        )
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in required",
        )

    user_id = _decode_bearer_token(token)
    fleet_header = _normalize_fleet_id(x_fleet_id)
    membership = await _select_membership(db, user_id, fleet_header)
    try:
        role = FleetRole(membership.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No fleet access for this account",
        ) from None
    return Principal(user_id=user_id, fleet_id=membership.fleet_id, role=role)


def require_roles(*allowed: FleetRole) -> Callable[..., Any]:
    allowed_set = set(allowed)

    async def guard(
        principal: Principal = Depends(require_api_access),
    ) -> Principal:
        if principal.role not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission for that",
            )
        return principal

    return guard
