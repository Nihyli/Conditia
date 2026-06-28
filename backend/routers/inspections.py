from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.base import CaptureMetadata
from config import settings
from database import get_db
from dependencies import get_inspection_ingestion_service
from domain import CaptureAngle, FleetRole, IngestibleCaptureSource
from models.db_models import Finding, Inspection, InspectionMedia, Truck
from models.schemas import (
    FindingOut,
    InspectionCreate,
    InspectionOut,
    InspectionSummary,
    MediaOut,
    UploadResult,
)
from security import Principal, require_api_access, require_roles
from services.analysis_jobs import run_analysis_job
from services.inspection_ingestion import (
    InspectionConflict,
    InspectionIngestionService,
)
from services.inspection_queries import build_inspection_summaries
from services.storage import StorageError

router = APIRouter(prefix="/inspections", tags=["inspections"])

async def _get_authorized_inspection(
    db: AsyncSession,
    inspection_id: UUID | str,
    principal: Principal,
) -> Inspection | None:
    statement = select(Inspection).where(Inspection.id == str(inspection_id))
    if principal.fleet_id is not None:
        statement = statement.join(Truck).where(Truck.fleet_id == principal.fleet_id)
    return (await db.execute(statement)).scalar_one_or_none()


@router.post("", response_model=InspectionOut, status_code=201)
async def create_inspection(
    payload: InspectionCreate,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_roles(FleetRole.INSPECTOR, FleetRole.ADMIN)),
    ingestion: InspectionIngestionService = Depends(
        get_inspection_ingestion_service
    ),
):
    truck_id = str(payload.truck_id)
    truck_statement = select(Truck).where(Truck.id == truck_id)
    if principal.fleet_id is not None:
        truck_statement = truck_statement.where(Truck.fleet_id == principal.fleet_id)
    truck = (await db.execute(truck_statement)).scalar_one_or_none()
    if truck is None:
        raise HTTPException(404, "Truck not found")
    return await ingestion.start(
        db,
        truck_id=truck_id,
        source=payload.capture_source,
        created_by=principal.user_id,
    )


@router.get("", response_model=list[InspectionSummary])
async def list_inspections(
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_api_access),
):
    statement = select(Inspection)
    if principal.fleet_id is not None:
        statement = statement.join(Truck).where(Truck.fleet_id == principal.fleet_id)
    result = await db.execute(statement.order_by(Inspection.started_at.desc()).limit(limit))
    inspections = result.scalars().all()
    return await build_inspection_summaries(db, list(inspections))


@router.get("/{inspection_id}", response_model=InspectionSummary)
async def get_inspection(
    inspection_id: UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_api_access),
):
    inspection = await _get_authorized_inspection(db, inspection_id, principal)
    if inspection is None:
        raise HTTPException(404, "Inspection not found")
    return (await build_inspection_summaries(db, [inspection]))[0]


@router.get("/{inspection_id}/findings", response_model=list[FindingOut])
async def inspection_findings(
    inspection_id: UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_api_access),
):
    if await _get_authorized_inspection(db, inspection_id, principal) is None:
        raise HTTPException(404, "Inspection not found")
    inspection_key = str(inspection_id)
    result = await db.execute(
        select(Finding)
        .where(Finding.inspection_id == inspection_key)
        .order_by(Finding.id.asc())
    )
    return result.scalars().all()


@router.get("/{inspection_id}/media", response_model=list[MediaOut])
async def inspection_media(
    inspection_id: UUID,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_api_access),
):
    inspection = await _get_authorized_inspection(db, inspection_id, principal)
    if inspection is None:
        raise HTTPException(404, "Inspection not found")
    inspection_key = str(inspection_id)
    result = await db.execute(
        select(InspectionMedia)
        .where(InspectionMedia.inspection_id == inspection_key)
        .order_by(InspectionMedia.captured_at.asc())
    )
    return result.scalars().all()


@router.post("/{inspection_id}/upload", response_model=UploadResult)
async def upload_media(
    inspection_id: UUID,
    files: list[UploadFile] = File(...),
    capture_angle: CaptureAngle = Form(...),
    capture_source: IngestibleCaptureSource = Form(IngestibleCaptureSource.MOBILE),
    gps_lat: float | None = Form(None),
    gps_lng: float | None = Form(None),
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_roles(FleetRole.INSPECTOR, FleetRole.ADMIN)),
    ingestion: InspectionIngestionService = Depends(
        get_inspection_ingestion_service
    ),
):
    inspection_key = str(inspection_id)
    inspection = await _get_authorized_inspection(db, inspection_key, principal)
    if inspection is None:
        raise HTTPException(404, "Inspection not found")
    if not files:
        raise HTTPException(400, "At least one media file is required")
    if len(files) > settings.max_files_per_upload:
        raise HTTPException(
            413,
            f"At most {settings.max_files_per_upload} files are allowed per upload",
        )
    if gps_lat is not None and not -90 <= gps_lat <= 90:
        raise HTTPException(422, "gps_lat must be between -90 and 90")
    if gps_lng is not None and not -180 <= gps_lng <= 180:
        raise HTTPException(422, "gps_lng must be between -180 and 180")

    metadata = CaptureMetadata(gps_lat=gps_lat, gps_lng=gps_lng)

    try:
        result = await ingestion.ingest(
            db,
            inspection=inspection,
            files=files,
            angle=capture_angle,
            source=capture_source,
            metadata=metadata,
        )
    except InspectionConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except StorageError as exc:
        raise HTTPException(400, str(exc)) from exc

    return UploadResult(
        uploaded=result.uploaded,
        source=result.source,
        status="media_uploaded",
        inspection_id=inspection_key,
    )


@router.post("/{inspection_id}/finalize", response_model=InspectionOut)
async def finalize_inspection(
    inspection_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(require_roles(FleetRole.INSPECTOR, FleetRole.ADMIN)),
    ingestion: InspectionIngestionService = Depends(
        get_inspection_ingestion_service
    ),
):
    inspection_key = str(inspection_id)
    inspection = await _get_authorized_inspection(db, inspection_key, principal)
    if inspection is None:
        raise HTTPException(404, "Inspection not found")
    try:
        result = await ingestion.finalize(db, inspection=inspection)
    except InspectionConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    background_tasks.add_task(run_analysis_job, result.job_id)
    return result.inspection
