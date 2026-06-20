from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from database import init_db
from routers import findings, fleet, inspections, reports, trucks


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 50)
    print("Conditia API v0.2.0")
    print(f"  storage: {settings.storage_dir}")
    print(f"  database: {settings.database_url}")
    print("=" * 50)
    await init_db()
    if settings.seed_on_startup:
        from seed import seed_if_empty

        await seed_if_empty()
    yield


app = FastAPI(
    title="Conditia API",
    version="0.1.0",
    description="Hardware-agnostic asset-condition intelligence platform.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve locally-stored media (dev mode). In production this is Supabase Storage.
_storage = Path(settings.storage_dir)
_storage.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(_storage)), name="media")

app.include_router(fleet.router)
app.include_router(trucks.router)
app.include_router(inspections.router)
app.include_router(findings.router)
app.include_router(reports.router)


@app.get("/health", tags=["meta"])
async def health():
    return {
        "status": "ok",
        "version": "0.2.0",
        "features": ["inspection_media", "media_sync", "fleet_stats"],
        "database": settings.database_url.split("://", 1)[0],
        "storage_dir": settings.storage_dir,
        "vision": "google" if settings.google_vision_enabled else "stub",
    }


@app.get("/", tags=["meta"])
async def root():
    return {"name": "Conditia API", "docs": "/docs"}
