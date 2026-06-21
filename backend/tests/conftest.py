from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

TEST_ROOT = Path(tempfile.mkdtemp(prefix="conditia-tests-"))
TEST_STORAGE = TEST_ROOT / "storage"

# Settings and infrastructure singletons are created at import time, so establish
# an isolated environment before importing application modules.
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = (
    f"sqlite+aiosqlite:///{(TEST_ROOT / 'test.db').as_posix()}"
)
os.environ["STORAGE_DIR"] = str(TEST_STORAGE)
os.environ["AUTH_MODE"] = "disabled"
os.environ["SEED_ON_STARTUP"] = "false"

from database import Base, engine  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture(autouse=True)
async def reset_state() -> AsyncGenerator[None, None]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    shutil.rmtree(TEST_STORAGE, ignore_errors=True)
    TEST_STORAGE.mkdir(parents=True, exist_ok=True)
    yield


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as value:
        yield value


def pytest_sessionfinish(session, exitstatus) -> None:
    del session, exitstatus
    shutil.rmtree(TEST_ROOT, ignore_errors=True)
