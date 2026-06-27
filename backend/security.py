"""Who is calling, and what they're allowed to do."""

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from domain import FleetRole
from models.db_models import FleetMembership


@dataclass(frozen=True)
class Principal:
    user_id: str | None
    fleet_id: str | None
    role: FleetRole | None

    @property
    def is_service(self) -> bool:
        return self.user_id is None and self.role == FleetRole.ADMIN


def _decode_bearer_token(token: str) -> str:
    if settings.jwt_secret is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT auth is not configured",
        )
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"require": ["sub", "exp"]},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        ) from None
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )
    return subject


async def _membership_for_user(
    db: AsyncSession, user_id: str
) -> FleetMembership | None:
    result = await db.execute(
        select(FleetMembership)
        .where(FleetMembership.user_id == user_id)
        .order_by(FleetMembership.fleet_id.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def require_api_access(
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> Principal:
    if settings.auth_mode == "disabled":
        return Principal(user_id=None, fleet_id=None, role=FleetRole.ADMIN)

    if settings.auth_mode == "api_key":
        if settings.api_key is None or x_api_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        if not secrets.compare_digest(x_api_key, settings.api_key):
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
    membership = await _membership_for_user(db, user_id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No fleet access for this account",
        )
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
