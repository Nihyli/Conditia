from datetime import datetime, timedelta, timezone

import jwt

from services.jwt_verify import decode_access_token_subject

SECRET = "test-jwt-secret-at-least-32-characters-long"
USER_ID = "22222222-2222-2222-2222-222222222222"


def _mint_hs256(*, secret: str = SECRET, user_id: str = USER_ID) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": user_id,
            "aud": "authenticated",
            "iat": now,
            "exp": now + timedelta(hours=1),
        },
        secret,
        algorithm="HS256",
    )


def test_decode_access_token_subject_accepts_hs256() -> None:
    from config import settings

    original = settings.jwt_secret
    settings.jwt_secret = SECRET
    try:
        assert decode_access_token_subject(_mint_hs256()) == USER_ID
    finally:
        settings.jwt_secret = original


def test_decode_access_token_subject_rejects_garbage() -> None:
    from config import settings

    original = settings.jwt_secret
    settings.jwt_secret = SECRET
    try:
        try:
            decode_access_token_subject("not-a-jwt")
        except ValueError as exc:
            assert "invalid" in str(exc).lower()
        else:
            raise AssertionError("expected ValueError")
    finally:
        settings.jwt_secret = original
