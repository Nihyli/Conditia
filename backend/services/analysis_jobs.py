"""Durable database-backed dispatch for inspection analysis."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, update

from database import SessionLocal
from domain import AnalysisJobStatus, InspectionStatus
from models.db_models import AnalysisJob, Inspection
from services.analysis import analyze_inspection

logger = logging.getLogger(__name__)


async def run_analysis_job(job_id: str) -> None:
    """Atomically claim one pending job; duplicate delivery is a no-op."""
    async with SessionLocal() as db:
        claim = await db.execute(
            update(AnalysisJob)
            .where(
                AnalysisJob.id == job_id,
                AnalysisJob.status == AnalysisJobStatus.PENDING.value,
            )
            .values(
                status=AnalysisJobStatus.RUNNING.value,
                attempts=AnalysisJob.attempts + 1,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()
        if claim.rowcount != 1:
            return

    try:
        await analyze_inspection_for_job(job_id)
    except Exception:
        logger.exception("Analysis job dispatch failed", extra={"job_id": job_id})
        async with SessionLocal() as db:
            job = await db.get(AnalysisJob, job_id)
            if job is not None:
                job.status = AnalysisJobStatus.FAILED.value
                job.last_error = "Unexpected analysis dispatcher failure"
                await db.commit()


async def analyze_inspection_for_job(job_id: str) -> None:
    async with SessionLocal() as db:
        job = await db.get(AnalysisJob, job_id)
        if job is None:
            return
        inspection_id = job.inspection_id

    await analyze_inspection(inspection_id)

    async with SessionLocal() as db:
        job = await db.get(AnalysisJob, job_id)
        inspection = await db.get(Inspection, inspection_id)
        if job is None or inspection is None:
            return
        if inspection.status in (
            InspectionStatus.COMPLETE.value,
            InspectionStatus.REVIEW_REQUIRED.value,
        ):
            job.status = AnalysisJobStatus.COMPLETE.value
            job.last_error = None
        elif inspection.status == InspectionStatus.FAILED.value:
            job.status = AnalysisJobStatus.FAILED.value
            job.last_error = "Inspection analysis failed"
        else:
            job.status = AnalysisJobStatus.FAILED.value
            job.last_error = "Inspection did not reach a terminal state"
        job.updated_at = datetime.now(timezone.utc)
        await db.commit()


async def resume_incomplete_analysis_jobs() -> None:
    """Reclaim work interrupted after a process crash and run pending jobs."""
    async with SessionLocal() as db:
        result = await db.execute(
            select(AnalysisJob).where(
                AnalysisJob.status.in_(
                    (AnalysisJobStatus.PENDING.value, AnalysisJobStatus.RUNNING.value)
                )
            )
        )
        jobs = list(result.scalars().all())
        for job in jobs:
            if job.status == AnalysisJobStatus.RUNNING.value:
                inspection = await db.get(Inspection, job.inspection_id)
                if (
                    inspection is not None
                    and inspection.status == InspectionStatus.PROCESSING.value
                ):
                    inspection.status = InspectionStatus.SUBMITTED.value
                job.status = AnalysisJobStatus.PENDING.value
                job.last_error = "Reclaimed after interrupted worker"
        await db.commit()
        job_ids = [job.id for job in jobs]

    for job_id in job_ids:
        await run_analysis_job(job_id)
