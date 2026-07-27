"""Small shared helpers."""

SEVERITY_RANK = {"critical": 3, "medium": 2, "low": 1, "clear": 0}


def normalize_severity(severity: str) -> str:
    """Collapse provisional ``high`` from the detector into ``critical``."""
    return "critical" if severity == "high" else severity


def worst_severity(severities: list[str]) -> str:
    if not severities:
        return "clear"
    return max(
        (normalize_severity(s) for s in severities),
        key=lambda s: SEVERITY_RANK.get(s, 0),
    )
