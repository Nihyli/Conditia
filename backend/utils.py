"""Small shared helpers."""

SEVERITY_RANK = {"critical": 3, "high": 3, "medium": 2, "low": 1, "clear": 0}


def normalize_severity(severity: str) -> str:
    return "critical" if severity == "high" else severity


def worst_severity(severities: list[str]) -> str:
    if not severities:
        return "clear"
    worst = max(severities, key=lambda s: SEVERITY_RANK.get(s, 0))
    return normalize_severity(worst)
