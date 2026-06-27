"""Seed a demo fleet so the API returns meaningful data immediately.

    python seed.py
    python seed.py --force
"""

import argparse
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from database import SessionLocal, init_db, is_postgres, run_migrations
from models.db_models import Finding, Fleet, Inspection, InspectionMedia, Report, Truck
from services import report_generator

_now = datetime.now(timezone.utc)
DEMO_FLEET_NAME = "Midwest Freight Co."

TRUCKS = [
    {
        "plate": "TRK-041", "vin": "1FUJGLDR0CSBT0041",
        "make": "Freightliner", "model": "Cascadia", "year": 2021,
        "minutes_ago": 6,
        "findings": [
            {"title": "Structural dent", "finding_type": "dent",
             "severity": "critical", "confidence": 0.94, "zone": "trailer_rear",
             "location": "Rear passenger corner", "ago": 0},
            {"title": "Paint scratch", "finding_type": "scratch",
             "severity": "medium", "confidence": 0.87, "zone": "trailer_mid",
             "location": "Driver side panel", "ago": 3},
            {"title": "Mirror misalignment", "finding_type": "anomaly",
             "severity": "low", "confidence": 0.79, "zone": "cab",
             "location": "Passenger side mirror", "ago": 1},
        ],
    },
    {
        "plate": "TRK-017", "vin": "1XKYDP9X7MJ000017",
        "make": "Kenworth", "model": "T680", "year": 2022,
        "minutes_ago": 29,
        "findings": [
            {"title": "Surface rust", "finding_type": "rust",
             "severity": "medium", "confidence": 0.82, "zone": "front",
             "location": "Front bumper", "ago": 5},
            {"title": "Tire sidewall wear", "finding_type": "anomaly",
             "severity": "low", "confidence": 0.71, "zone": "front",
             "location": "Front driver axle", "ago": 2},
        ],
    },
    {
        "plate": "TRK-088", "vin": "1XPBDP9X1ND000088",
        "make": "Peterbilt", "model": "579", "year": 2020,
        "minutes_ago": 58,
        "findings": [
            {"title": "Cracked headlight", "finding_type": "crack",
             "severity": "critical", "confidence": 0.90, "zone": "front",
             "location": "Driver side front", "ago": 0},
        ],
    },
    {
        "plate": "TRK-062", "vin": "4V4NC9EH7MN000062",
        "make": "Volvo", "model": "VNL 860", "year": 2023,
        "minutes_ago": 82,
        "findings": [],
    },
    {
        "plate": "TRK-033", "vin": "1M1AN4GY8LM000033",
        "make": "Mack", "model": "Anthem", "year": 2019,
        "minutes_ago": 60 * 30,
        "findings": [
            {"title": "Trailer panel dent", "finding_type": "dent",
             "severity": "medium", "confidence": 0.85, "zone": "trailer_mid",
             "location": "Mid trailer, driver side", "ago": 4},
        ],
    },
]


async def _clear_fleet_data(db) -> None:
    await db.execute(delete(Finding))
    await db.execute(delete(Report))
    await db.execute(delete(InspectionMedia))
    await db.execute(delete(Inspection))
    await db.execute(delete(Truck))
    await db.execute(delete(Fleet))
    await db.commit()


async def seed_if_empty() -> None:
    async with SessionLocal() as db:
        existing = await db.execute(select(Fleet).limit(1))
        if existing.scalar_one_or_none() is not None:
            return
        await _seed(db)


async def seed_demo(*, force: bool = False) -> None:
    async with SessionLocal() as db:
        if force:
            await _clear_fleet_data(db)
        else:
            existing = await db.execute(select(Fleet).limit(1))
            if existing.scalar_one_or_none() is not None:
                print("Database already has data. Use --force to replace it.")
                return
        await _seed(db)
    print(f'Demo fleet "{DEMO_FLEET_NAME}" seeded ({len(TRUCKS)} trucks).')


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
    parser.add_argument("--force", action="store_true", help="Clear existing data first")
    args = parser.parse_args()

    if is_postgres():
        run_migrations()
    else:
        await init_db()

    await seed_demo(force=args.force)


if __name__ == "__main__":
    asyncio.run(_main())
