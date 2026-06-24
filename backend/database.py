import ssl as ssl_lib
from collections.abc import AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import settings


class Base(DeclarativeBase):
    pass


def _build_async_url(raw_url: str) -> tuple[str, dict]:
    """Normalize a database URL for SQLAlchemy's async engine.

    - Rewrites bare Postgres URLs (``postgres://`` / ``postgresql://``) to the
      asyncpg driver so Supabase connection strings work as pasted.
    - Strips libpq-only ``sslmode`` query args (asyncpg rejects them) and turns
      them into an asyncpg ``ssl`` connect arg, following libpq semantics:
      ``require`` (the Supabase default) encrypts without verifying the chain,
      while ``verify-ca`` / ``verify-full`` verify it. SSL is enabled
      automatically for ``*.supabase.co`` / ``*.supabase.com`` hosts.
    - Disables asyncpg's statement cache, which is required when connecting
      through the Supabase transaction pooler (PgBouncer).
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
    require_ssl = sslmode in ("require", "verify-ca", "verify-full") or is_supabase
    if require_ssl:
        ctx = ssl_lib.create_default_context()
        # Only verify-ca / verify-full check the certificate chain. The default
        # (require) encrypts but skips verification — matching libpq and how
        # Supabase connection strings are issued (managed pooler certs are not
        # in the system trust store).
        if sslmode not in ("verify-ca", "verify-full"):
            ctx.check_hostname = False
            ctx.verify_mode = ssl_lib.CERT_NONE
        connect_args["ssl"] = ctx

    # PgBouncer (Supabase transaction pooler) does not support prepared
    # statements; disabling the cache keeps the unnamed-statement path.
    connect_args["statement_cache_size"] = 0
    return raw_url, connect_args


_async_url, _connect_args = _build_async_url(settings.database_url)

engine = create_async_engine(
    _async_url, echo=False, future=True, connect_args=_connect_args
)

SessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a request-scoped async session."""
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create any missing tables. Works on both SQLite (dev) and Postgres/
    Supabase — db/schema.sql is an optional native-typed alternative."""
    # Import models so they register on Base.metadata before create_all.
    from models import db_models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
