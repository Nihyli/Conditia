from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import HTTPException

from config import settings


def create_local_token(*, user_id: str, email: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iss": "conditia-local",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    return token if isinstance(token, str) else token.decode("utf-8")


def decode_token(token: str) -> dict[str, Any]:
    """Validate a local or Supabase JWT and return claims."""
    if settings.auth_provider == "supabase":
        try:
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        except jwt.PyJWTError as exc:
            raise HTTPException(status_code=401, detail="Invalid token") from exc

    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            options={"require": ["sub", "exp"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
