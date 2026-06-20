from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.drone import DroneAdapter
from adapters.mobile import MobileAdapter
from database import get_db
from models.db_models import Finding, Inspection, InspectionMedia, Truck
from models.schemas import (
    FindingOut,
    InspectionCreate,
    InspectionOut,
    InspectionSummary,
    UploadResult,
)
from services.analysis import analyze_inspection
from services.inspection_history import inspections_since_first_seen
from utils import worst_severity

router = APIRouter(prefix="/inspections", tags=["inspections"])

# Adapter registry. Adding a capture source = registering an adapter here.
ADAPTERS = {
    "mobile": MobileAdapter(),
    "drone": DroneAdapter(),  # stubbed -> 501 until Phase 5
}

VIDEO_EXTS = (".mp4", ".mov", ".webm", ".avi")


def _truck_label(truck: Truck | None) -> str:
    if truck is None:
        return "Unknown truck"
    plate = truck.license_plate
    return plate or truck.vin


async def _build_summary(db: AsyncSession, inspection: Inspection) -> InspectionSummary:
    truck = await db.get(Truck, inspection.truck_id)
    result = await db.execute(
        select(Finding).where(Finding.inspection_id == inspection.id)
    )
    findings = result.scalars().all()

    finding_outs: list[FindingOut] = []
    for f in findings:
        ago = await inspections_since_first_seen(
            db=db,
            truck_id=inspection.truck_id,
            current_inspection_id=inspection.id,
            first_seen_inspection_id=f.first_seen_inspection_id,
        )
        base = FindingOut.model_validate(f)
        finding_outs.append(
            base.model_copy(update={"first_detected_inspections_ago": ago})
        )

    return InspectionSummary(
        id=inspection.id,
        truck_id=inspection.truck_id,
        truck_label=_truck_label(truck),
        make=truck.make if truck else None,
        model=truck.model if truck else None,
        started_at=inspection.started_at,
        status=inspection.status,
        capture_source=inspection.capture_source,
        finding_count=len(finding_outs),
        worst_severity=worst_severity([f.severity for f in findings]),
        findings=finding_outs,
    )


@router.post("", response_model=InspectionOut, status_code=201)
async def create_inspection(
    payload: InspectionCreate, db: AsyncSession = Depends(get_db)
):
    truck = await db.get(Truck, payload.truck_id)
    if truck is None:
        raise HTTPException(404, "Truck not found")
    inspection = Inspection(
        truck_id=payload.truck_id,
        capture_source=payload.capture_source,
        created_by=payload.created_by,
        status="pending",
    )
    db.add(inspection)
    await db.commit()
    await db.refresh(inspection)
    return inspection


@router.get("", response_model=list[InspectionSummary])
async def list_inspections(limit: int = 25, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Inspection).order_by(Inspection.started_at.desc()).limit(limit)
    )
    inspections = result.scalars().all()
    return [await _build_summary(db, i) for i in inspections]


@router.get("/{inspection_id}", response_model=InspectionSummary)
async def get_inspection(inspection_id: str, db: AsyncSession = Depends(get_db)):
    inspection = await db.get(Inspection, inspection_id)
    if inspection is None:
        raise HTTPException(404, "Inspection not found")
    return await _build_summary(db, inspection)


@router.get("/{inspection_id}/findings", response_model=list[FindingOut])
async def inspection_findings(
    inspection_id: str, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Finding).where(Finding.inspection_id == inspection_id)
    )
    return result.scalars().all()


@router.post("/{inspection_id}/upload", response_model=UploadResult)
async def upload_media(
    inspection_id: str,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    capture_angle: str = Form(...),
    capture_source: str = Form("mobile"),
    gps_lat: float | None = Form(None),
    gps_lng: float | None = Form(None),
    drone_flight_id: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    inspection = await db.get(Inspection, inspection_id)
    if inspection is None:
        raise HTTPException(404, "Inspection not found")

    adapter = ADAPTERS.get(capture_source)
    if adapter is None:
        raise HTTPException(400, f"Unknown capture source: {capture_source}")

    metadata = {
        "gps_lat": gps_lat,
        "gps_lng": gps_lng,
        "drone_flight_id": drone_flight_id,
    }

    try:
        paths = await adapter.receive_media(
            inspection_id, files, capture_angle, metadata
        )
    except NotImplementedError as exc:
        raise HTTPException(501, str(exc)) from exc

    for path in paths:
        is_video = path.lower().endswith(VIDEO_EXTS)
        db.add(
            InspectionMedia(
                inspection_id=inspection_id,
                media_type="video" if is_video else "photo",
                capture_angle=capture_angle,
                capture_source=adapter.get_source_name(),
                drone_flight_id=metadata.get("drone_flight_id"),
                storage_path=path,
                gps_lat=metadata.get("gps_lat"),
                gps_lng=metadata.get("gps_lng"),
            )
        )
    inspection.capture_source = adapter.get_source_name()
    inspection.status = "pending"
    await db.commit()

    # Same analysis pipeline regardless of capture source.
    background_tasks.add_task(analyze_inspection, inspection_id)

    return UploadResult(
        uploaded=len(paths),
        source=capture_source,
        status="analysis_queued",
        inspection_id=inspection_id,
    )
