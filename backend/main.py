import asyncio
import logging
import time
from contextlib import asynccontextmanager, suppress
from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db, init_db, is_postgres, run_migrations
from routers import (
    auth,
    findings,
    fleet,
    inspections,
    media,
    memberships,
    reports,
    trucks,
)
from security import require_api_access
from services.analysis_jobs import resume_incomplete_analysis_jobs

APP_VERSION = "0.3.0"
logger = logging.getLogger(__name__)


_TOO_LARGE_BODY = b'{"detail":"Request body is too large"}'


class MaxBodySizeMiddleware:
    """Count actual body bytes so chunked / unlabeled requests can't exceed the
    cap by omitting Content-Length (the header is only a hint). The limit is read
    per request so it stays in sync with settings.

    On overflow we send a 413 directly and feed the app a disconnect, then
    suppress the app's own response. Raising instead would be swallowed by
    FastAPI's body parser and surface as a generic 400.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        received = 0
        max_bytes = settings.max_request_bytes
        rejected = False

        async def counting_receive():
            nonlocal received, rejected
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > max_bytes and not rejected:
                    rejected = True
                    await send(
                        {
                            "type": "http.response.start",
                            "status": 413,
                            "headers": [
                                (b"content-type", b"application/json"),
                                (b"x-content-type-options", b"nosniff"),
                            ],
                        }
                    )
                    await send(
                        {"type": "http.response.body", "body": _TOO_LARGE_BODY}
                    )
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message):
            if rejected:
                return
            await send(message)

        await self.app(scope, counting_receive, guarded_send)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting Conditia API",
        extra={
            "version": APP_VERSION,
            "environment": settings.environment,
            "database_dialect": settings.database_url.split(":", 1)[0],
        },
    )
    if settings.environment != "production":
        if is_postgres():
            run_migrations()
        else:
            await init_db()
    if settings.seed_on_startup:
        from seed import seed_if_empty

        await seed_if_empty()
    resume_task = asyncio.create_task(resume_incomplete_analysis_jobs())
    try:
        yield
    finally:
        if not resume_task.done():
            resume_task.cancel()
            with suppress(asyncio.CancelledError):
                await resume_task


app = FastAPI(
    title="Conditia API",
    version=APP_VERSION,
    description="Hardware-agnostic asset-condition intelligence platform.",
    lifespan=lifespan,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)

app.add_middleware(MaxBodySizeMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-API-Key",
        "X-Request-ID",
        "X-Fleet-ID",
    ],
    expose_headers=["X-Request-ID"],
)


_DOCS_PATHS = frozenset({"/docs", "/redoc", "/openapi.json"})


def _add_security_headers(response, request_id: str, *, csp: bool = True):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(self), geolocation=()"
    response.headers["X-Request-ID"] = request_id
    if csp:
        # This service only serves JSON; lock everything down. Skipped for the
        # Swagger/ReDoc pages (dev only) which load assets from a CDN.
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        )
    return response


# ponytail: per-process fixed-window counter, keyed by client IP. Real
# multi-instance limiting belongs at the gateway / a shared store (Redis).
_rate_window: dict[str, tuple[int, float]] = {}
_rate_lock = asyncio.Lock()


async def _is_rate_limited(key: str, limit: int) -> bool:
    now = time.monotonic()
    async with _rate_lock:
        count, started = _rate_window.get(key, (0, now))
        if now - started >= 60:
            count, started = 0, now
        count += 1
        _rate_window[key] = (count, started)
        return count > limit


@app.middleware("http")
async def security_headers(request: Request, call_next):
    request_id = str(uuid4())
    request.state.request_id = request_id
    csp = request.url.path not in _DOCS_PATHS or not settings.docs_enabled

    limit = settings.rate_limit_per_minute
    if limit > 0:
        client = request.client.host if request.client else "unknown"
        if await _is_rate_limited(client, limit):
            return _add_security_headers(
                JSONResponse(status_code=429, content={"detail": "Too many requests"}),
                request_id,
                csp=csp,
            )

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > settings.max_request_bytes:
                return _add_security_headers(
                    JSONResponse(
                        status_code=413,
                        content={"detail": "Request body is too large"},
                    ),
                    request_id,
                    csp=csp,
                )
        except ValueError:
            return _add_security_headers(
                JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header"},
                ),
                request_id,
                csp=csp,
            )
    response = await call_next(request)
    return _add_security_headers(response, request_id, csp=csp)


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", str(uuid4()))
    logger.error(
        "Unhandled request failure",
        extra={"request_id": request_id, "path": request.url.path},
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return _add_security_headers(
        JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "request_id": request_id,
            },
        ),
        request_id,
    )


api_router = APIRouter(dependencies=[Depends(require_api_access)])
api_router.include_router(auth.router)
api_router.include_router(fleet.router)
api_router.include_router(memberships.router)
api_router.include_router(trucks.router)
api_router.include_router(inspections.router)
api_router.include_router(media.router)
api_router.include_router(findings.router)
api_router.include_router(reports.router)
app.include_router(api_router)


@app.get("/health", tags=["meta"])
async def health():
    return {
        "status": "ok",
        "version": APP_VERSION,
        "features": ["inspection_media", "explicit_finalize", "fleet_stats"],
        "database": settings.database_url.split("://", 1)[0],
        "vision": "experimental_google" if settings.google_vision_enabled else "unavailable",
    }


@app.get("/ready", tags=["meta"])
async def readiness(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"status": "ready", "version": APP_VERSION}


@app.get("/", tags=["meta"])
async def root():
    return {
        "name": "Conditia API",
        "docs": "/docs" if settings.docs_enabled else None,
    }
