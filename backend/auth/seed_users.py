"""Seed demo user accounts for local auth."""

from sqlalchemy import select

from auth.passwords import hash_password
from auth.roles import UserRole
from database import SessionLocal
from models.db_models import User

DEMO_PASSWORD = "demo1234"

DEMO_USERS: list[tuple[str, str, UserRole]] = [
    ("admin@conditia.ai", "Admin User", UserRole.ADMIN),
    ("manager@conditia.ai", "Fleet Manager", UserRole.FLEET_MANAGER),
    ("inspector@conditia.ai", "Field Inspector", UserRole.INSPECTOR),
    ("viewer@conditia.ai", "Read-only Viewer", UserRole.VIEWER),
]


async def seed_users_if_empty() -> None:
    async with SessionLocal() as db:
        existing = await db.execute(select(User).limit(1))
        if existing.scalar_one_or_none() is not None:
            return

        for email, full_name, role in DEMO_USERS:
            db.add(
                User(
                    email=email,
                    password_hash=hash_password(DEMO_PASSWORD),
                    full_name=full_name,
                    role=role.value,
                    auth_provider="local",
                )
            )
        await db.commit()


async def _main() -> None:
    from database import init_db

    await init_db()
    await seed_users_if_empty()
    print(f"Demo users ready (password: {DEMO_PASSWORD})")
    for email, _, role in DEMO_USERS:
        print(f"  {email} — {role.value}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(_main())
