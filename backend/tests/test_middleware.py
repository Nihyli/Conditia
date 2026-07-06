from __future__ import annotations

import pytest
from httpx import AsyncClient

import main
from config import settings


@pytest.mark.asyncio
async def test_security_headers_include_csp(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert (
        response.headers["content-security-policy"]
        == "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    )
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
async def test_rate_limit_returns_429_over_budget(client: AsyncClient) -> None:
    original = settings.rate_limit_per_minute
    main._rate_window.clear()
    settings.rate_limit_per_minute = 3
    try:
        statuses = [(await client.get("/health")).status_code for _ in range(4)]
    finally:
        settings.rate_limit_per_minute = original
        main._rate_window.clear()
    assert statuses[:3] == [200, 200, 200]
    assert statuses[3] == 429


@pytest.mark.asyncio
async def test_chunked_body_over_limit_is_rejected(client: AsyncClient) -> None:
    original = settings.max_request_bytes
    settings.max_request_bytes = 1024
    try:
        # An async generator body sends chunked with no Content-Length, so only
        # the streaming byte counter can catch it.
        async def oversized():
            yield b"x" * 4096

        response = await client.post("/trucks", content=oversized())
    finally:
        settings.max_request_bytes = original
    assert response.status_code == 413
    assert response.headers["x-content-type-options"] == "nosniff"
