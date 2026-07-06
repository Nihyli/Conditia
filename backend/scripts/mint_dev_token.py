#!/usr/bin/env python3
"""Create a local sign-in token for JWT auth mode.

Usage:
  python scripts/mint_dev_token.py
  python scripts/mint_dev_token.py --role admin
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import settings  # noqa: E402
from database import SessionLocal, init_db, is_postgres, run_migrations  # noqa: E402
from domain import FleetRole  # noqa: E402
from models.db_models import Fleet, FleetMembership  # noqa: E402
from seed import DEMO_FLEET_NAME  # noqa: E402

DEV_USER_ID = "11111111-1111-1111-1111-111111111111"
DEV_EMAIL = "driver@conditia.local"
DEFAULT_DEV_SECRET = "conditia-local-dev-jwt-secret-change-me-32chars"


def _resolve_secret() -> str:
    secret = settings.jwt_secret or os.environ.get("JWT_SECRET")
    if secret and len(secret) >= 32:
        return secret
    return DEFAULT_DEV_SECRET


async def _ensure_membership(role: FleetRole) -> tuple[str, str]:
    if is_postgres():
        run_migrations()
    else:
        await init_db()

    async with SessionLocal() as db:
        fleet = (
            await db.execute(select(Fleet).where(Fleet.name == DEMO_FLEET_NAME))
        ).scalar_one_or_none()
        if fleet is None:
            fleet = Fleet(name=DEMO_FLEET_NAME)
            db.add(fleet)
            await db.flush()

        membership = await db.get(
            FleetMembership, {"fleet_id": fleet.id, "user_id": DEV_USER_ID}
        )
        if membership is None:
            db.add(
                FleetMembership(
                    fleet_id=fleet.id,
                    user_id=DEV_USER_ID,
                    role=role.value,
                )
            )
        else:
            membership.role = role.value
        await db.commit()
        return DEV_USER_ID, fleet.id


def _mint_token(*, user_id: str, secret: str, hours: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": DEV_EMAIL,
        "aud": "authenticated",
        "iat": now,
        "exp": now + timedelta(hours=hours),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


async def main() -> None:
    if settings.environment == "production":
        raise SystemExit("mint_dev_token.py must not run in production")
    parser = argparse.ArgumentParser(description="Mint a local JWT for Conditia.")
    parser.add_argument(
        "--role",
        choices=[role.value for role in FleetRole],
        default=FleetRole.INSPECTOR.value,
        help="Fleet role to attach in fleet_memberships",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Token lifetime in hours",
    )
    args = parser.parse_args()

    secret = _resolve_secret()
    user_id, fleet_id = await _ensure_membership(FleetRole(args.role))
    token = _mint_token(user_id=user_id, secret=secret, hours=args.hours)

    print()
    print("Local JWT ready. Backend .env should include:")
    print("  AUTH_MODE=jwt")
    print(f"  JWT_SECRET={secret}")
    print()
    print("Paste this in the app sign-in screen, or export it for curl:")
    print(f'  export CONDITIA_TOKEN="{token}"')
    print()
    print(f"User:  {DEV_EMAIL} ({user_id})")
    print(f"Fleet: {fleet_id}")
    print(f"Role:  {args.role}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
