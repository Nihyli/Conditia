"""Verify the configured database is reachable and the schema is in place.

Useful when wiring up Supabase Postgres. Run after setting DATABASE_URL:

    python check_db.py

It connects, prints the server identity (with the password masked), ensures all
tables exist via create_all, and reports current row counts.
"""

import asyncio

from sqlalchemy import text

from config import settings
from database import engine, init_db


async def main() -> None:
    scheme = settings.database_url.split("://", 1)[0]
    is_postgres = "postgres" in scheme

    print("Conditia DB check")
    print(f"  configured scheme : {scheme}")
    print(f"  engine url        : {engine.url.render_as_string(hide_password=True)}")

    try:
        async with engine.connect() as conn:
            if is_postgres:
                server = await conn.scalar(text("SELECT version()"))
            else:
                server = await conn.scalar(text("SELECT sqlite_version()"))
                server = f"SQLite {server}"
        print(f"  connection        : OK")
        print(f"  server            : {server}")
    except Exception as exc:  # noqa: BLE001 — surface the raw driver error
        print(f"  connection        : FAILED")
        print(f"  error             : {type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc

    await init_db()
    print("  tables            : ensured (create_all)")

    # Imported lazily so a connection failure above reports first.
    from seed import data_status

    status = await data_status()
    print("  row counts        :")
    for key, value in status.items():
        print(f"      {key:<16}: {value}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
