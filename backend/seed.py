"""Seed a demo fleet so the API returns meaningful data immediately.

Mirrors the dashboard's mock fleet (Midwest Freight Co.). Runs automatically on
startup when SEED_ON_STARTUP=true and the DB is empty, or manually:

    python seed.py
    python seed.py --force
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, func, select

from config import settings
from database import SessionLocal, init_db
from models.db_models import (
    Finding,
    Fleet,
    Inspection,
    InspectionMedia,
    Report,
    Truck,
)
from services import report_generator

_now = datetime.now(timezone.utc)
DEMO_FLEET_NAME = "Midwest Freight Co."

TRUCKS = [
    {
        "plate": "TRK-041",
        "vin": "1FUJGLDR0CSBT0041",
        "make": "Freightliner",
        "model": "Cascadia",
        "year": 2021,
        "minutes_ago": 6,
        "findings": [
            {
                "title": "Structural dent",
                "finding_type": "dent",
                "severity": "critical",
                "confidence": 0.94,
                "zone": "trailer_rear",
                "location": "Rear passenger corner",
                "ago": 0,
            },
            {
                "title": "Paint scratch",
                "finding_type": "scratch",
                "severity": "medium",
                "confidence": 0.87,
                "zone": "trailer_mid",
                "location": "Driver side panel",
                "ago": 3,
            },
            {
                "title": "Mirror misalignment",
                "finding_type": "anomaly",
                "severity": "low",
                "confidence": 0.79,
                "zone": "cab",
                "location": "Passenger side mirror",
                "ago": 1,
            },
        ],
    },
    {
        "plate": "TRK-017",
        "vin": "1XKYDP9X7MJ000017",
        "make": "Kenworth",
        "model": "T680",
        "year": 2022,
        "minutes_ago": 29,
        "findings": [
            {
                "title": "Surface rust",
                "finding_type": "rust",
                "severity": "medium",
                "confidence": 0.82,
                "zone": "front",
                "location": "Front bumper",
                "ago": 5,
            },
            {
                "title": "Tire sidewall wear",
                "finding_type": "anomaly",
                "severity": "low",
                "confidence": 0.71,
                "zone": "front",
                "location": "Front driver axle",
                "ago": 2,
            },
        ],
    },
    {
        "plate": "TRK-088",
        "vin": "1XPBDP9X1ND000088",
        "make": "Peterbilt",
        "model": "579",
        "year": 2020,
        "minutes_ago": 58,
        "findings": [
            {
                "title": "Cracked headlight",
                "finding_type": "crack",
                "severity": "critical",
                "confidence": 0.90,
                "zone": "front",
                "location": "Driver side front",
                "ago": 0,
            },
        ],
    },
    {
        "plate": "TRK-062",
        "vin": "4V4NC9EH7MN000062",
        "make": "Volvo",
        "model": "VNL 860",
        "year": 2023,
        "minutes_ago": 82,
        "findings": [],
    },
    {
        "plate": "TRK-033",
        "vin": "1M1AN4GY8LM000033",
        "make": "Mack",
        "model": "Anthem",
        "year": 2019,
        "minutes_ago": 60 * 30,
        "findings": [
            {
                "title": "Trailer panel dent",
                "finding_type": "dent",
                "severity": "medium",
                "confidence": 0.85,
                "zone": "trailer_mid",
                "location": "Mid trailer, driver side",
                "ago": 4,
            },
        ],
    },
]


async def count_rows(db) -> dict[str, int]:
    return {
        "fleets": int(await db.scalar(select(func.count()).select_from(Fleet)) or 0),
        "trucks": int(await db.scalar(select(func.count()).select_from(Truck)) or 0),
        "inspections": int(
            await db.scalar(select(func.count()).select_from(Inspection)) or 0
        ),
        "findings": int(
            await db.scalar(select(func.count()).select_from(Finding)) or 0
        ),
        "media": int(
            await db.scalar(select(func.count()).select_from(InspectionMedia)) or 0
        ),
        "reports": int(await db.scalar(select(func.count()).select_from(Report)) or 0),
    }


def count_storage_files() -> int:
    base = Path(settings.storage_dir)
    if not base.exists():
        return 0
    return sum(1 for path in base.rglob("*") if path.is_file())


def clear_storage_dir() -> int:
    """Remove all files under the storage directory. Returns files removed."""
    base = Path(settings.storage_dir)
    removed = count_storage_files()
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)
    return removed


async def clear_all_data(db, *, clear_storage: bool = True) -> dict[str, int]:
    """Delete all fleet data. Returns row counts that were cleared."""
    before = await count_rows(db)

    await db.execute(delete(Finding))
    await db.execute(delete(Report))
    await db.execute(delete(InspectionMedia))
    await db.execute(delete(Inspection))
    await db.execute(delete(Truck))
    await db.execute(delete(Fleet))
    await db.commit()

    storage_files = clear_storage_dir() if clear_storage else 0
    return {
        "fleets": before["fleets"],
        "trucks": before["trucks"],
        "inspections": before["inspections"],
        "findings": before["findings"],
        "media": before["media"],
        "reports": before["reports"],
        "storage_files": storage_files,
    }


async def seed_if_empty() -> None:
    async with SessionLocal() as db:
        existing = await db.execute(select(Fleet).limit(1))
        if existing.scalar_one_or_none() is not None:
            return
        await _seed(db)


async def seed_demo(*, force: bool = False) -> dict:
    """Insert the Midwest Freight demo fleet. Optionally wipe existing data first."""
    async with SessionLocal() as db:
        counts = await count_rows(db)
        has_data = counts["fleets"] > 0 or counts["trucks"] > 0

        if has_data and not force:
            return {
                "seeded": False,
                "message": "Database already has data. Use force=true to replace it.",
                "counts": counts,
            }

        if has_data and force:
            await clear_all_data(db, clear_storage=True)

        await _seed(db)
        after = await count_rows(db)
        return {
            "seeded": True,
            "message": f"Demo fleet “{DEMO_FLEET_NAME}” seeded ({len(TRUCKS)} trucks).",
            "counts": after,
        }


async def unseed(*, clear_storage: bool = True) -> dict:
    """Remove all fleet data from the database and optionally storage."""
    async with SessionLocal() as db:
        cleared = await clear_all_data(db, clear_storage=clear_storage)
        return {
            "cleared": True,
            "message": "All fleet data removed.",
            "cleared_counts": cleared,
        }


async def data_status() -> dict:
    async with SessionLocal() as db:
        counts = await count_rows(db)
    counts["storage_files"] = count_storage_files()
    counts["has_data"] = counts["trucks"] > 0 or counts["inspections"] > 0
    counts["demo_fleet_name"] = DEMO_FLEET_NAME
    return counts


async def _seed(db) -> None:
    fleet = Fleet(name=DEMO_FLEET_NAME)
    db.add(fleet)
    await db.flush()

    for spec in TRUCKS:
        truck = Truck(
            fleet_id=fleet.id,
            vin=spec["vin"],
            make=spec["make"],
            model=spec["model"],
            year=spec["year"],
            license_plate=spec["plate"],
        )
        db.add(truck)
        await db.flush()

        started = _now - timedelta(minutes=spec["minutes_ago"])
        inspection = Inspection(
            truck_id=truck.id,
            started_at=started,
            completed_at=started + timedelta(minutes=4),
            status="complete",
            capture_source="mobile",
        )
        db.add(inspection)
        await db.flush()

        for f in spec["findings"]:
            db.add(
                Finding(
                    inspection_id=inspection.id,
                    title=f["title"],
                    finding_type=f["finding_type"],
                    severity=f["severity"],
                    confidence=f["confidence"],
                    zone=f["zone"],
                    location=f["location"],
                    description=f["title"],
                    first_seen_inspection_id=inspection.id,
                )
            )
        await db.flush()
        await report_generator.generate(db, inspection.id)

    await db.commit()


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Seed Conditia demo fleet")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Clear existing data before seeding",
    )
    args = parser.parse_args()

    await init_db()
    result = await seed_demo(force=args.force)
    print(result["message"])


if __name__ == "__main__":
    asyncio.run(_main())
