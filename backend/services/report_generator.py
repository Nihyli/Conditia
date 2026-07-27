"""Report generation. Computes a structured summary per inspection.

PDF export is left as a follow-up (pdf_path stays NULL); raw_json holds the full
structured report for downstream integrations and the dashboard's PDF export.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.db_models import Finding, Report

SEVERITY_ORDER = ("critical", "medium", "low", "clear")


def _build_narrative_markdown(
    inspection_id: str,
    summary: str,
    findings: list[Finding],
    *,
    requires_human_review: bool,
) -> str:
    """Build a deterministic markdown narrative from structured findings."""
    total = len(findings)
    critical = sum(1 for f in findings if f.severity == "critical")
    medium = sum(1 for f in findings if f.severity == "medium")
    low = sum(1 for f in findings if f.severity == "low")

    lines: list[str] = [
        "## Conditia Condition Report",
        "",
        f"**Inspection:** `{inspection_id}`",
        "",
        "### Executive Summary",
        "",
        summary,
        "",
    ]

    if requires_human_review:
        lines += [
            "> **Manual review required** — automated triage results are "
            "provisional and do not constitute a clear assessment.",
            "",
        ]

    if total == 0:
        lines += [
            "No findings were detected during this inspection.",
            "",
        ]
    else:
        lines += [
            f"**{total}** finding{'s' if total != 1 else ''} detected: "
            f"**{critical}** critical, **{medium}** medium, **{low}** low.",
            "",
        ]

        by_severity: dict[str, list[Finding]] = {}
        for f in findings:
            by_severity.setdefault(f.severity, []).append(f)

        for sev in SEVERITY_ORDER:
            group = by_severity.get(sev)
            if not group:
                continue
            lines += [
                f"### {sev.capitalize()} ({len(group)})",
                "",
            ]
            for f in group:
                title = f.title or f.finding_type
                loc = f.location or f.zone or "Unknown location"
                conf = round(f.confidence * 100)
                lines.append(f"- **{title}** — {loc} ({conf}% confidence, {f.status})")
            lines.append("")

    lines += [
        "### Recommended Next Steps",
        "",
    ]
    if requires_human_review:
        lines.append("1. Assign a qualified reviewer to validate all provisional findings.")
    if critical:
        lines.append(
            f"1. Address **{critical}** critical finding{'s' if critical != 1 else ''} "
            "before returning the vehicle to service."
        )
    if medium or low:
        lines.append("1. Schedule repairs for medium and low severity items per fleet policy.")
    if total > 0:
        lines.append("1. Re-inspect after repairs to confirm resolution.")
    if total == 0 and not requires_human_review:
        lines.append("1. No action required. Vehicle may continue normal operations.")
    lines.append("")

    return "\n".join(lines)


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

    narrative_md = _build_narrative_markdown(
        inspection_id,
        summary,
        list(findings),
        requires_human_review=requires_human_review,
    )

    raw_json = {
        "inspection_id": inspection_id,
        "total_findings": total,
        "critical_findings": critical,
        "requires_human_review": requires_human_review,
        "narrative_markdown": narrative_md,
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
