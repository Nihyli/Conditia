from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import select

from config import settings
from database import SessionLocal
from models.db_models import (
    AnalysisJob,
    Finding,
    Inspection,
    InspectionMedia,
    Report,
    Truck,
)
from services import analysis_jobs
from services.analysis import (
    AnalysisDependencies,
    FrameExtractionUnavailable,
    analyze_inspection,
    extract_frames,
)
from services.report_generator import generate as generate_report
from services.storage import storage_service
from services.vision import (
    Detection,
    DetectionBatch,
    DetectionFailed,
    DetectorUnavailable,
    _classify_damage_type,
    _provisional_severity,
    detect_damage,
)


def test_detection_classification_and_provisional_severity() -> None:
    assert _classify_damage_type("Large DENT") == "dent"
    assert _classify_damage_type("missing mirror") == "missing_component"
    assert _classify_damage_type("vehicle damage") == "anomaly"
    assert _provisional_severity(0.95) == "high"
    assert _provisional_severity(0.8) == "medium"
    assert _provisional_severity(0.5) == "low"


@pytest.mark.asyncio
async def test_detector_unavailable_is_explicit(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "google_application_credentials", None)
    with pytest.raises(DetectorUnavailable):
        await detect_damage(tmp_path / "image.png")


def install_fake_vision(monkeypatch, response) -> None:
    vision = ModuleType("google.cloud.vision")

    class Image:
        def __init__(self, content):
            self.content = content

    class Client:
        def label_detection(self, *, image):
            assert image.content == b"image"
            if isinstance(response, Exception):
                raise response
            return response

    vision.Image = Image
    vision.ImageAnnotatorClient = Client
    cloud = ModuleType("google.cloud")
    cloud.vision = vision
    google = ModuleType("google")
    google.cloud = cloud
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud)
    monkeypatch.setitem(sys.modules, "google.cloud.vision", vision)


@pytest.mark.asyncio
async def test_google_detection_filters_labels_and_requires_review(
    monkeypatch,
    tmp_path: Path,
) -> None:
    image = tmp_path / "image.png"
    image.write_bytes(b"image")
    response = SimpleNamespace(
        error=SimpleNamespace(message=""),
        label_annotations=[
            SimpleNamespace(description="Vehicle", score=0.99),
            SimpleNamespace(description="Deep scratch", score=0.91),
            SimpleNamespace(description="Missing mirror", score=0.8),
        ],
    )
    install_fake_vision(monkeypatch, response)
    monkeypatch.setattr(settings, "google_application_credentials", "configured")

    batch = await detect_damage(image)

    assert [item.finding_type for item in batch.detections] == [
        "scratch",
        "missing_component",
    ]
    assert batch.detections[0].severity == "high"
    assert batch.requires_human_review is True
    assert batch.detector == "google-label-detection-experimental"


@pytest.mark.asyncio
async def test_google_detection_hides_provider_failures(monkeypatch, tmp_path: Path) -> None:
    image = tmp_path / "image.png"
    image.write_bytes(b"image")
    monkeypatch.setattr(settings, "google_application_credentials", "configured")
    install_fake_vision(
        monkeypatch,
        SimpleNamespace(
            error=SimpleNamespace(message="quota detail"),
            label_annotations=[],
        ),
    )
    with pytest.raises(DetectionFailed, match="returned an error"):
        await detect_damage(image)

    install_fake_vision(monkeypatch, RuntimeError("provider secret"))
    with pytest.raises(DetectionFailed, match="Damage detector failed"):
        await detect_damage(image)


def test_extract_frames_for_image_and_invalid_video(monkeypatch, tmp_path: Path) -> None:
    image = tmp_path / "image.png"
    assert extract_frames(image, tmp_path) == [image]

    class ClosedCapture:
        def __init__(self, path):
            assert path.endswith("video.mp4")

        def isOpened(self):
            return False

        def release(self):
            pass

    monkeypatch.setitem(
        sys.modules,
        "cv2",
        SimpleNamespace(VideoCapture=ClosedCapture),
    )
    with pytest.raises(FrameExtractionUnavailable, match="could not be decoded"):
        extract_frames(tmp_path / "video.mp4", tmp_path)


def test_extract_frames_writes_sampled_video_frames(monkeypatch, tmp_path: Path) -> None:
    class Capture:
        reads = iter(((True, "frame-1"), (True, "frame-2"), (False, None)))

        def __init__(self, path):
            del path

        def isOpened(self):
            return True

        def get(self, prop):
            del prop
            return 2

        def read(self):
            return next(self.reads)

        def release(self):
            pass

    def write(path, frame):
        Path(path).write_text(frame)
        return True

    monkeypatch.setitem(
        sys.modules,
        "cv2",
        SimpleNamespace(VideoCapture=Capture, CAP_PROP_FPS=5, imwrite=write),
    )
    frames = extract_frames(tmp_path / "video.webm", tmp_path, interval_seconds=1)
    assert [path.name for path in frames] == ["frame_0.jpg"]
    assert frames[0].read_text() == "frame-1"


async def create_submitted_inspection() -> tuple[str, str]:
    async with SessionLocal() as db:
        truck = Truck(vin="1FUJGLDR0CSBT0041")
        db.add(truck)
        await db.flush()
        inspection = Inspection(truck_id=truck.id, status="submitted")
        db.add(inspection)
        await db.flush()
        path = f"{inspection.id}/front/image.png"
        media = InspectionMedia(
            inspection_id=inspection.id,
            media_type="photo",
            capture_angle="front",
            capture_source="mobile",
            storage_path=path,
        )
        db.add(media)
        await db.commit()
        storage_path = storage_service.abs_path(path)
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        storage_path.write_bytes(b"image")
        return inspection.id, media.id


@pytest.mark.asyncio
async def test_analysis_success_persists_findings_and_report() -> None:
    inspection_id, media_id = await create_submitted_inspection()

    async def fake_detect(path):
        assert path.name == "image.png"
        return DetectionBatch(
            detections=[
                Detection(
                    finding_type="dent",
                    severity="medium",
                    confidence=0.88,
                    description="Detected dent",
                    zone="front",
                    location="Bumper",
                )
            ],
            requires_human_review=False,
            detector="fake",
        )

    await analyze_inspection(
        inspection_id,
        AnalysisDependencies(
            storage=storage_service,
            detector=fake_detect,
            report_builder=generate_report,
        ),
    )

    async with SessionLocal() as db:
        inspection = await db.get(Inspection, inspection_id)
        finding = (
            await db.execute(select(Finding).where(Finding.inspection_id == inspection_id))
        ).scalar_one()
        report = (
            await db.execute(select(Report).where(Report.inspection_id == inspection_id))
        ).scalar_one()
    assert inspection.status == "complete"
    assert inspection.completed_at is not None
    assert finding.media_id == media_id
    assert finding.first_seen_inspection_id == inspection_id
    assert report.total_findings == 1
    assert "1 finding" in report.summary


@pytest.mark.asyncio
async def test_analysis_unexpected_failure_sets_failed() -> None:
    inspection_id, _ = await create_submitted_inspection()

    async def fail(path):
        del path
        raise RuntimeError("unexpected")

    await analyze_inspection(
        inspection_id,
        AnalysisDependencies(
            storage=storage_service,
            detector=fail,
            report_builder=generate_report,
        ),
    )
    async with SessionLocal() as db:
        inspection = await db.get(Inspection, inspection_id)
    assert inspection.status == "failed"
    assert inspection.completed_at is not None


@pytest.mark.asyncio
async def test_analysis_job_dispatch_and_terminal_failures(monkeypatch) -> None:
    inspection_id, _ = await create_submitted_inspection()
    async with SessionLocal() as db:
        job = AnalysisJob(inspection_id=inspection_id, status="pending")
        db.add(job)
        await db.commit()
        job_id = job.id

    async def dispatch_failure(job_id_arg):
        assert job_id_arg == job_id
        raise RuntimeError("worker failed")

    monkeypatch.setattr(analysis_jobs, "analyze_inspection_for_job", dispatch_failure)
    await analysis_jobs.run_analysis_job(job_id)
    async with SessionLocal() as db:
        failed_job = await db.get(AnalysisJob, job_id)
    assert failed_job.status == "failed"
    assert failed_job.last_error == "Unexpected analysis dispatcher failure"


@pytest.mark.asyncio
async def test_analysis_job_marks_nonterminal_and_missing_jobs(monkeypatch) -> None:
    inspection_id, _ = await create_submitted_inspection()
    async with SessionLocal() as db:
        inspection = await db.get(Inspection, inspection_id)
        inspection.status = "processing"
        job = AnalysisJob(inspection_id=inspection_id, status="running")
        db.add(job)
        await db.commit()
        job_id = job.id

    async def no_op(inspection_id_arg):
        assert inspection_id_arg == inspection_id

    monkeypatch.setattr(analysis_jobs, "analyze_inspection", no_op)
    await analysis_jobs.analyze_inspection_for_job(job_id)
    await analysis_jobs.analyze_inspection_for_job(str(UUID(int=0)))

    async with SessionLocal() as db:
        job = await db.get(AnalysisJob, job_id)
    assert job.status == "failed"
    assert job.last_error == "Inspection did not reach a terminal state"
