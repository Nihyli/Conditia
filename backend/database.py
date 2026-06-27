import ssl as ssl_lib
from collections.abc import AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import settings


class Base(DeclarativeBase):
    pass


def build_async_url(raw_url: str) -> tuple[str, dict]:
    """Normalize a database URL for SQLAlchemy's async engine and Alembic.

    - Rewrites bare Postgres URLs (``postgres://`` / ``postgresql://``) to the
      asyncpg driver so Supabase connection strings work as pasted.
    - Strips the libpq-only ``sslmode`` query arg (asyncpg rejects it) and turns
      it into an asyncpg ``ssl`` connect arg following libpq semantics:
      ``require`` (and the Supabase default) encrypts without verifying the
      chain, while ``verify-ca`` / ``verify-full`` verify it. TLS is enabled
      automatically for ``*.supabase.co`` / ``*.supabase.com`` hosts.
    - Disables asyncpg's statement cache, required when connecting through the
      Supabase transaction pooler (PgBouncer).

    Returns the normalized URL and a ``connect_args`` dict for the engine.
    """
    connect_args: dict = {}

    if raw_url.startswith("postgres://"):
        raw_url = "postgresql://" + raw_url[len("postgres://") :]
    if raw_url.startswith("postgresql://"):
        raw_url = "postgresql+asyncpg://" + raw_url[len("postgresql://") :]

    if "+asyncpg" not in raw_url:
        return raw_url, connect_args

    parts = urlsplit(raw_url)
    query = dict(parse_qsl(parts.query))
    sslmode = query.pop("sslmode", None)
    raw_url = urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )

    host = parts.hostname or ""
    is_supabase = host.endswith(("supabase.co", "supabase.com"))
    if sslmode in ("require", "verify-ca", "verify-full") or is_supabase:
        ctx = ssl_lib.create_default_context()
        # Only verify-ca / verify-full check the certificate chain. The default
        # (require) encrypts but skips verification — matching libpq and how
        # Supabase pooler certs are issued (not in the system trust store).
        if sslmode not in ("verify-ca", "verify-full"):
            ctx.check_hostname = False
            ctx.verify_mode = ssl_lib.CERT_NONE
        connect_args["ssl"] = ctx

    connect_args["statement_cache_size"] = 0
    return raw_url, connect_args


async_database_url, _connect_args = build_async_url(settings.database_url)

engine = create_async_engine(
    async_database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
    connect_args=_connect_args,
)


if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
        del connection_record
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a request-scoped async session."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Bootstrap SQLite for local dev. Postgres/Supabase schema is Alembic-managed."""
    from models import db_models  # noqa: F401

    if not settings.database_url.startswith("sqlite"):
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def run_migrations() -> None:
    """Apply Alembic migrations through head (Postgres / Supabase).

    Runs in a subprocess so it works from FastAPI's async lifespan (Alembic's
    env.py uses asyncio.run, which cannot nest inside uvicorn's event loop).
    """
    import subprocess
    import sys
    from pathlib import Path

    backend_dir = Path(__file__).resolve().parent
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "unknown error").strip()
        raise RuntimeError(f"alembic upgrade head failed:\n{detail}")


def is_postgres() -> bool:
    url = settings.database_url
    return url.startswith("postgres") or url.startswith("postgresql")
