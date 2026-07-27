"""Decode bearer tokens from local HS256 dev minting or Supabase Auth."""

from __future__ import annotations

import logging
from typing import Any

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientError, PyJWTError

from config import settings

logger = logging.getLogger(__name__)

_jwks_client_instance: PyJWKClient | None = None


def _supabase_jwks_url() -> str | None:
    if not settings.supabase_url:
        return None
    return f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"


def _get_jwks_client() -> PyJWKClient | None:
    global _jwks_client_instance
    url = _supabase_jwks_url()
    if url is None:
        return None
    if _jwks_client_instance is None:
        _jwks_client_instance = PyJWKClient(url, cache_keys=True)
    return _jwks_client_instance


def _decode_kwargs() -> dict[str, Any]:
    decode_kwargs: dict[str, Any] = {
        "audience": "authenticated",
        "options": {"require": ["sub", "exp"]},
    }
    if settings.jwt_issuer:
        decode_kwargs["issuer"] = settings.jwt_issuer
    return decode_kwargs


def _subject_from_payload(payload: dict[str, Any]) -> str | None:
    subject = payload.get("sub")
    if isinstance(subject, str) and subject:
        return subject
    return None


def _decode_with_jwks(token: str) -> str | None:
    client = _get_jwks_client()
    if client is None:
        return None
    try:
        signing_key = client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256", "EdDSA"],
            **_decode_kwargs(),
        )
    except (PyJWKClientError, PyJWTError):
        return None
    return _subject_from_payload(payload)


def _decode_with_hs256(token: str) -> str | None:
    if settings.jwt_secret is None:
        return None
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            **_decode_kwargs(),
        )
    except PyJWTError:
        return None
    return _subject_from_payload(payload)


def decode_access_token_subject(token: str) -> str:
    """Return the authenticated user id (JWT ``sub``) or raise ValueError."""
    subject = _decode_with_jwks(token)
    if subject is None:
        subject = _decode_with_hs256(token)
    if subject is None:
        logger.info("auth.jwt_rejected", extra={"reason": "invalid_or_expired"})
        raise ValueError("invalid or expired session")
    return subject
