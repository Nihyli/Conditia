"""Main analysis pipeline.

Runs as a background task after upload. The media's `capture_source` is
irrelevant here -- mobile, drone, and fixed-camera footage all flow through the
exact same pipeline. That is the whole point of the adapter architecture.
"""

from datetime import datetime, timezone

from sqlalchemy import select

from database import SessionLocal
from models.db_models import Finding, Inspection, InspectionMedia
from services import report_generator
from services.change_detection import find_first_occurrence
from services.vision import detect_damage


def extract_frames(storage_path: str, interval_seconds: int = 2) -> list[str]:
    """Best-effort frame extraction. Uses OpenCV when available for videos;
    otherwise treats the media as a single frame. Never raises."""
    if not storage_path.lower().endswith((".mp4", ".mov", ".webm", ".avi")):
        return [storage_path]
    try:  # OpenCV is optional.
        import cv2  # type: ignore

        from services.storage import storage_service

        abs_path = str(storage_service.abs_path(storage_path))
        cap = cv2.VideoCapture(abs_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        step = int(fps * interval_seconds) or 1
        frames: list[str] = []
        idx = 0
        saved = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % step == 0:
                frame_path = f"{storage_path}.frame_{saved}.jpg"
                cv2.imwrite(str(storage_service.abs_path(frame_path)), frame)
                frames.append(frame_path)
                saved += 1
            idx += 1
        cap.release()
        return frames or [storage_path]
    except Exception:
        return [storage_path]


async def analyze_inspection(inspection_id: str) -> None:
    """Fetch media, detect damage, run change detection, persist findings,
    generate the report, and mark the inspection complete."""
    async with SessionLocal() as db:
        inspection = await db.get(Inspection, inspection_id)
        if inspection is None:
            return

        inspection.status = "processing"
        await db.commit()

        try:
            media_result = await db.execute(
                select(InspectionMedia).where(
                    InspectionMedia.inspection_id == inspection_id
                )
            )
            media_items = media_result.scalars().all()

            for media in media_items:
                frames = extract_frames(media.storage_path)
                for frame_path in frames:
                    detections = await detect_damage(frame_path)
                    for det in detections:
                        first_seen = await find_first_occurrence(
                            db=db,
                            truck_id=inspection.truck_id,
                            finding_type=det.finding_type,
                            zone=det.zone,
                            current_inspection_id=inspection_id,
                        )
                        db.add(
                            Finding(
                                inspection_id=inspection_id,
                                media_id=media.id,
                                title=det.description or det.finding_type.title(),
                                finding_type=det.finding_type,
                                severity=det.severity,
                                confidence=det.confidence,
                                zone=det.zone,
                                location=det.location,
                                bounding_box=det.bounding_box,
                                description=det.description,
                                first_seen_inspection_id=first_seen,
                            )
                        )
            await db.commit()

            await report_generator.generate(db, inspection_id)

            inspection.completed_at = datetime.now(timezone.utc)
            inspection.status = "complete"
            await db.commit()
        except Exception:
            inspection.status = "failed"
            await db.commit()
            raise
