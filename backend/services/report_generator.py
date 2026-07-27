"""Report generation. Computes a structured summary per inspection.

PDF export is left as a follow-up (pdf_path stays NULL); raw_json holds the full
structured report for downstream integrations and the dashboard's PDF export.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.db_models import Finding, Report


async def generate(
    db: AsyncSession,
    inspection_id: str,
    *,
    requires_human_review: bool = False,
) -> Report:
    result = await db.execute(
        select(Finding).where(Finding.inspection_id == inspection_id)
    )
    findings = result.scalars().all()

    total = len(findings)
    critical = sum(1 for f in findings if f.severity == "critical")

    if requires_human_review and total == 0:
        summary = (
            "Automated triage finished, but manual review is required. "
            "No clear result was issued."
        )
    elif requires_human_review:
        summary = (
            f"Automated triage produced {total} provisional finding"
            f"{'' if total == 1 else 's'}. Manual review is required."
        )
    elif total == 0:
        summary = "Inspection complete. No findings detected."
    else:
        summary = (
            f"Inspection complete. {total} finding"
            f"{'' if total == 1 else 's'} detected"
            f"{f', {critical} critical' if critical else ''}."
        )

    raw_json = {
        "inspection_id": inspection_id,
        "total_findings": total,
        "critical_findings": critical,
        "requires_human_review": requires_human_review,
        "findings": [
            {
                "id": f.id,
                "title": f.title,
                "type": f.finding_type,
                "severity": f.severity,
                "confidence": f.confidence,
                "status": f.status,
                "zone": f.zone,
                "location": f.location,
                "first_seen_inspection_id": f.first_seen_inspection_id,
            }
            for f in findings
        ],
    }

    # Upsert: one report per inspection.
    existing = await db.execute(
        select(Report).where(Report.inspection_id == inspection_id)
    )
    report = existing.scalar_one_or_none()
    if report is None:
        report = Report(inspection_id=inspection_id)
        db.add(report)

    report.summary = summary
    report.total_findings = total
    report.critical_findings = critical
    report.raw_json = raw_json

    await db.flush()
    return report
