"""Short-lived HMAC tokens for browser media delivery without Authorization headers."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from uuid import UUID

from config import settings

_TOKEN_VERSION = "v1"


def _signing_material() -> bytes:
    if settings.jwt_secret:
        return settings.jwt_secret.encode()
    if settings.api_key:
        return settings.api_key.encode()
    return b"conditia-dev-media-token-key"


def mint_media_access_token(
    media_id: str,
    *,
    fleet_id: str | None,
    user_id: str | None,
) -> tuple[str, int]:
    """Return (token, expires_at_unix) for embedding in a media delivery URL."""
    ttl = settings.media_token_ttl_seconds
    expires_at = int(time.time()) + ttl
    scope = fleet_id or ""
    actor = user_id or ""
    payload = f"{_TOKEN_VERSION}:{media_id}:{scope}:{actor}:{expires_at}"
    digest = hmac.new(
        _signing_material(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"{payload}:{digest}", expires_at


def verify_media_access_token(media_id: str, token: str) -> bool:
    parts = token.split(":")
    if len(parts) != 6 or parts[0] != _TOKEN_VERSION:
        return False
    _, token_media_id, _scope, _actor, expires_raw, digest = parts
    if token_media_id != media_id:
        return False
    try:
        expires_at = int(expires_raw)
    except ValueError:
        return False
    if expires_at < int(time.time()):
        return False
    payload = ":".join(parts[:-1])
    expected = hmac.new(
        _signing_material(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return secrets.compare_digest(digest, expected)


def media_content_path(media_id: UUID | str, token: str) -> str:
    return f"/inspection-media/{media_id}/content?access_token={token}"
