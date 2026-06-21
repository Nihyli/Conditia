from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.jwt_utils import decode_token
from auth.roles import UserRole, role_at_least
from config import settings
from database import get_db
from models.db_models import User


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    if not settings.auth_enabled:
        return await _dev_bypass_user(db)

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.split(" ", 1)[1].strip()
    claims = decode_token(token)
    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = await db.get(User, str(user_id))
    if user is None and settings.auth_provider == "supabase":
        user = await _upsert_supabase_user(db, claims)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def _dev_bypass_user(db: AsyncSession) -> User:
    """Synthetic admin when AUTH_ENABLED=false (local tooling only)."""
    result = await db.execute(select(User).limit(1))
    user = result.scalar_one_or_none()
    if user is not None:
        return user
    user = User(
        email="dev@conditia.local",
        full_name="Dev User",
        role=UserRole.ADMIN,
        auth_provider="local",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _upsert_supabase_user(db: AsyncSession, claims: dict) -> User:
    user_id = str(claims["sub"])
    email = claims.get("email") or f"{user_id}@supabase.local"
    meta = claims.get("app_metadata") or {}
    role = meta.get("role") or claims.get("role") or UserRole.VIEWER

    user = User(
        id=user_id,
        email=email,
        full_name=meta.get("full_name") or email.split("@")[0],
        role=str(role),
        auth_provider="supabase",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def require_role(minimum: UserRole):
    async def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role == UserRole.ADMIN or role_at_least(user.role, minimum):
            return user
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    return _dep
