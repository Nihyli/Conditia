"""Damage detection.

If Google Cloud Vision is configured (GOOGLE_APPLICATION_CREDENTIALS), real
label detection runs. Otherwise detection is stubbed and returns no findings,
so the full pipeline (upload -> store -> analyze -> report) runs end to end with
zero external setup. Phase 3 replaces this with a fine-tuned YOLOv8 model.
"""

from dataclasses import dataclass, field

from config import settings

DAMAGE_KEYWORDS = (
    "dent", "scratch", "crack", "damage", "rust",
    "broken", "missing", "flat", "puncture", "tear",
)


@dataclass
class Detection:
    finding_type: str
    severity: str
    confidence: float
    description: str
    zone: str | None = None
    location: str | None = None
    bounding_box: dict | None = field(default=None)


def _classify_damage_type(label: str) -> str:
    label = label.lower()
    for key in ("dent", "scratch", "crack", "rust"):
        if key in label:
            return key
    if "missing" in label:
        return "missing_component"
    return "anomaly"


def _estimate_severity(score: float) -> str:
    if score >= 0.9:
        return "critical"
    if score >= 0.75:
        return "medium"
    return "low"


async def detect_damage(image_path: str) -> list[Detection]:
    """Return detections for a single frame/image path.

    Stubbed (returns []) unless Google Vision is configured.
    """
    if not settings.google_vision_enabled:
        return []

    # Real path: lazy import so the dependency is optional.
    try:
        from google.cloud import vision  # type: ignore

        from services.storage import storage_service

        client = vision.ImageAnnotatorClient()
        content = await storage_service.download(image_path)
        image = vision.Image(content=content)
        response = client.label_detection(image=image)

        detections: list[Detection] = []
        for label in response.label_annotations:
            desc = label.description.lower()
            if any(kw in desc for kw in DAMAGE_KEYWORDS):
                detections.append(
                    Detection(
                        finding_type=_classify_damage_type(desc),
                        severity=_estimate_severity(label.score),
                        confidence=float(label.score),
                        description=label.description,
                    )
                )
        return detections
    except Exception:
        # Detection must never crash the pipeline.
        return []
