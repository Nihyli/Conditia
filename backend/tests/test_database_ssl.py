from __future__ import annotations

import ssl
from pathlib import Path

import pytest

from config import Settings
from database import _build_ssl_context, build_async_url


def test_sqlite_url_has_no_ssl_connect_args() -> None:
    url, connect_args = build_async_url("sqlite+aiosqlite:///./test.db")
    assert url == "sqlite+aiosqlite:///./test.db"
    assert "ssl" not in connect_args


def test_supabase_url_enables_tls_by_default(tmp_path: Path, monkeypatch) -> None:
    from config import settings

    monkeypatch.setattr(settings, "database_ssl_ca", None)
    monkeypatch.setattr(settings, "database_ssl_insecure", False)

    url, connect_args = build_async_url(
        "postgresql://user:pass@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
    )
    assert "+asyncpg" in url
    assert "ssl" in connect_args
    ctx = connect_args["ssl"]
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.verify_mode == ssl.CERT_NONE


def test_ca_file_enables_certificate_verification(
    tmp_path: Path, monkeypatch
) -> None:
    from config import settings

    ca_file = tmp_path / "ca.pem"
    ca_file.write_text("placeholder")
    monkeypatch.setattr(settings, "database_ssl_ca", str(ca_file))
    monkeypatch.setattr(settings, "database_ssl_insecure", False)

    sentinel = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    monkeypatch.setattr(
        "database.ssl_lib.create_default_context", lambda **kwargs: sentinel
    )

    ctx = _build_ssl_context(sslmode="require", is_supabase=True)
    assert ctx is sentinel


def test_verify_full_checks_hostname(tmp_path: Path, monkeypatch) -> None:
    from config import settings

    ca_file = tmp_path / "ca.pem"
    ca_file.write_text("placeholder")
    monkeypatch.setattr(settings, "database_ssl_ca", str(ca_file))
    monkeypatch.setattr(settings, "database_ssl_insecure", False)

    created: list[ssl.SSLContext] = []

    def fake_create_default_context(**kwargs):
        del kwargs
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        created.append(ctx)
        return ctx

    monkeypatch.setattr(
        "database.ssl_lib.create_default_context", fake_create_default_context
    )

    ctx = _build_ssl_context(sslmode="verify-full", is_supabase=False)
    assert ctx is not None
    assert ctx.check_hostname is True


def test_database_ssl_insecure_opt_out(monkeypatch) -> None:
    from config import settings

    monkeypatch.setattr(settings, "database_ssl_ca", None)
    monkeypatch.setattr(settings, "database_ssl_insecure", True)
    monkeypatch.setattr(settings, "environment", "development")

    ctx = _build_ssl_context(sslmode="require", is_supabase=True)
    assert ctx is not None
    assert ctx.verify_mode == ssl.CERT_NONE


def test_sslmode_stripped_from_async_url() -> None:
    url, connect_args = build_async_url(
        "postgresql://user:pass@db.example.com:5432/app?sslmode=verify-full"
    )
    assert "sslmode" not in url
    assert "ssl" in connect_args


def test_production_rejects_unverified_postgres() -> None:
    with pytest.raises(ValueError, match="DATABASE_SSL_CA"):
        Settings(
            _env_file=None,
            environment="production",
            auth_mode="api_key",
            api_key="a" * 32,
            api_fleet_id="00000000-0000-0000-0000-000000000001",
            database_url="postgresql+asyncpg://user:password@db.example.com/app",
            storage_backend="supabase",
            supabase_url="https://example.supabase.co",
            supabase_key="service-role-key",
            docs_enabled=False,
            cors_origins="https://fleet.example.com",
            rate_limit_per_minute=120,
        )


def test_production_accepts_pinned_ca(tmp_path: Path) -> None:
    ca_file = tmp_path / "supabase-ca.crt"
    ca_file.write_text("placeholder")
    settings = Settings(
        _env_file=None,
        environment="production",
        auth_mode="api_key",
        api_key="a" * 32,
        api_fleet_id="00000000-0000-0000-0000-000000000001",
        database_url="postgresql+asyncpg://user:password@aws-0-us-east-1.pooler.supabase.com/postgres",
        database_ssl_ca=str(ca_file),
        storage_backend="supabase",
        supabase_url="https://example.supabase.co",
        supabase_key="service-role-key",
        docs_enabled=False,
        cors_origins="https://fleet.example.com",
        rate_limit_per_minute=120,
    )
    assert settings.database_ssl_ca == str(ca_file)


def test_production_rejects_missing_ca_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.crt"
    with pytest.raises(ValueError, match="not found"):
        Settings(
            _env_file=None,
            environment="production",
            auth_mode="api_key",
            api_key="a" * 32,
            api_fleet_id="00000000-0000-0000-0000-000000000001",
            database_url="postgresql+asyncpg://user:password@db.example.com/app",
            database_ssl_ca=str(missing),
            storage_backend="supabase",
            supabase_url="https://example.supabase.co",
            supabase_key="service-role-key",
            docs_enabled=False,
            cors_origins="https://fleet.example.com",
            rate_limit_per_minute=120,
        )
