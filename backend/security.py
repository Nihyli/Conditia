"""Transport authentication guard.

API-key mode is a deployment perimeter, not user/tenant authorization. A
fleet-scoped identity provider can replace this dependency without modifying
individual route handlers.
"""

import secrets
from dataclasses import dataclass

from fastapi import Header, HTTPException, status

from config import settings


@dataclass(frozen=True)
class Principal:
    fleet_id: str | None


async def require_api_access(
    x_api_key: str | None = Header(default=None),
) -> Principal:
    if settings.auth_mode == "disabled":
        return Principal(fleet_id=None)
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
    return Principal(
        fleet_id=str(settings.api_fleet_id) if settings.api_fleet_id else None
    )
