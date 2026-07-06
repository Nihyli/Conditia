"""Durable database-backed dispatch for inspection analysis.

Jobs are claimed under a lease (owner + expiry). Reclamation only touches leases
that have expired, so a restarting or newly-deployed instance never steals work
an instance is still running.
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import or_, select, update

from database import SessionLocal
from domain import AnalysisJobStatus, InspectionStatus
from models.db_models import AnalysisJob, Inspection
from services.analysis import analyze_inspection

logger = logging.getLogger(__name__)

# Identifies this process so reclamation can tell our work from a dead instance's.
_OWNER = uuid4().hex

# ponytail: fixed lease, no mid-run heartbeat. A job running longer than this can
# be reclaimed and double-run; raise the TTL or add a heartbeat if real analysis
# ever approaches it.
LEASE_TTL = timedelta(minutes=30)


async def run_analysis_job(job_id: str) -> None:
    """Atomically claim one pending job under a lease; duplicate delivery is a no-op."""
    now = datetime.now(timezone.utc)
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
                updated_at=now,
                lease_owner=_OWNER,
                lease_expires_at=now + LEASE_TTL,
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
                _release_lease(job)
                await db.commit()


def _release_lease(job: AnalysisJob) -> None:
    job.lease_owner = None
    job.lease_expires_at = None


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
        _release_lease(job)
        job.updated_at = datetime.now(timezone.utc)
        await db.commit()


async def resume_incomplete_analysis_jobs() -> None:
    """Reclaim only jobs whose lease expired, then run everything pending."""
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        stale = await db.execute(
            select(AnalysisJob).where(
                AnalysisJob.status == AnalysisJobStatus.RUNNING.value,
                or_(
                    AnalysisJob.lease_expires_at.is_(None),
                    AnalysisJob.lease_expires_at < now,
                ),
            )
        )
        for job in stale.scalars().all():
            inspection = await db.get(Inspection, job.inspection_id)
            if (
                inspection is not None
                and inspection.status == InspectionStatus.PROCESSING.value
            ):
                inspection.status = InspectionStatus.SUBMITTED.value
            job.status = AnalysisJobStatus.PENDING.value
            job.last_error = "Reclaimed after expired lease"
            _release_lease(job)
        await db.commit()

        pending = await db.execute(
            select(AnalysisJob.id).where(
                AnalysisJob.status == AnalysisJobStatus.PENDING.value
            )
        )
        job_ids = [row[0] for row in pending.all()]

    for job_id in job_ids:
        await run_analysis_job(job_id)
