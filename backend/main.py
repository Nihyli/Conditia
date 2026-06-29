import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db, init_db, is_postgres, run_migrations
from routers import auth, findings, fleet, inspections, media, memberships, reports, trucks
from security import require_api_access
from services.analysis_jobs import resume_incomplete_analysis_jobs

APP_VERSION = "0.3.0"
logger = logging.getLogger(__name__)


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


def _add_security_headers(response, request_id: str):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(self), geolocation=()"
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def security_headers(request: Request, call_next):
    request_id = str(uuid4())
    request.state.request_id = request_id
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
                )
        except ValueError:
            return _add_security_headers(
                JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid Content-Length header"},
                ),
                request_id,
            )
    response = await call_next(request)
    return _add_security_headers(response, request_id)


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
