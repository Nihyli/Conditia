"""Damage detection boundary.

Google label detection remains an experimental signal and is explicitly marked
as requiring human review. Infrastructure failure is never converted into a
valid empty finding set.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import anyio

from config import settings

logger = logging.getLogger(__name__)

DAMAGE_KEYWORDS = (
    "dent",
    "scratch",
    "crack",
    "damage",
    "rust",
    "broken",
    "missing",
    "flat",
    "puncture",
    "tear",
)


class DetectorUnavailable(Exception):
    pass


class DetectionFailed(Exception):
    pass


@dataclass
class Detection:
    finding_type: str
    severity: str
    confidence: float
    description: str
    zone: str | None = None
    location: str | None = None
    bounding_box: dict | None = field(default=None)


@dataclass(frozen=True)
class DetectionBatch:
    detections: list[Detection]
    requires_human_review: bool
    detector: str


def _classify_damage_type(label: str) -> str:
    label = label.lower()
    for key in ("dent", "scratch", "crack", "rust"):
        if key in label:
            return key
    if "missing" in label:
        return "missing_component"
    return "anomaly"


def _provisional_severity(score: float) -> str:
    """UI triage only; model confidence is not accepted as final severity."""
    if score >= 0.9:
        return "high"
    if score >= 0.75:
        return "medium"
    return "low"


async def detect_damage(image_path: Path) -> DetectionBatch:
    if not settings.google_vision_enabled:
        raise DetectorUnavailable("No damage detector is configured")

    try:
        from google.cloud import vision  # type: ignore

        content = await anyio.to_thread.run_sync(image_path.read_bytes)
        image = vision.Image(content=content)

        def call_google() -> object:
            client = vision.ImageAnnotatorClient()
            return client.label_detection(image=image)

        response = await anyio.to_thread.run_sync(call_google)
        if response.error.message:
            raise DetectionFailed("Detector returned an error")

        detections: list[Detection] = []
        for label in response.label_annotations:
            description = label.description or ""
            normalized = description.lower()
            if any(keyword in normalized for keyword in DAMAGE_KEYWORDS):
                detections.append(
                    Detection(
                        finding_type=_classify_damage_type(normalized),
                        severity=_provisional_severity(float(label.score)),
                        confidence=float(label.score),
                        description=description,
                    )
                )
        return DetectionBatch(
            detections=detections,
            requires_human_review=True,
            detector="google-label-detection-experimental",
        )
    except (DetectorUnavailable, DetectionFailed):
        raise
    except Exception as exc:
        logger.exception("Damage detector failed for media path")
        raise DetectionFailed("Damage detector failed") from exc
