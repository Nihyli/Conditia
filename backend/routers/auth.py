from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from auth.jwt_utils import create_local_token
from auth.passwords import verify_password
from config import settings
from database import get_db
from models.db_models import User
from models.schemas import AuthConfigOut, LoginRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/config", response_model=AuthConfigOut)
async def auth_config():
    return AuthConfigOut(
        auth_enabled=settings.auth_enabled,
        provider=settings.auth_provider,
        supabase_url=settings.supabase_url,
        supabase_anon_key=settings.supabase_anon_key,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    if settings.auth_provider == "supabase":
        raise HTTPException(
            status_code=400,
            detail="Use Supabase Auth on the client; this endpoint is for local dev only.",
        )

    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_local_token(user_id=user.id, email=user.email, role=user.role)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/sync", response_model=UserOut)
async def sync_supabase_user(
    user: User = Depends(get_current_user),
):
    """Return the profile for a Supabase-authenticated user (creates on first call)."""
    return UserOut.model_validate(user)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)
