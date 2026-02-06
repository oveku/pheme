"""Shared test fixtures for Pheme."""

import os
import pytest
import pytest_asyncio
import aiosqlite

# Override DB path before any imports
os.environ["PHEME_DB_PATH"] = ":memory:"
os.environ["SMTP_USER"] = "test@test.com"
os.environ["SMTP_PASSWORD"] = "testpass"
os.environ["DIGEST_RECIPIENT"] = "recipient@test.com"

from app.config import Settings, reset_settings
from app.database import init_db, get_db, close_db, _set_db


@pytest.fixture(autouse=True)
def _reset_config():
    """Reset settings singleton between tests."""
    reset_settings()
    yield
    reset_settings()


@pytest_asyncio.fixture
async def db():
    """Provide a fresh in-memory database for each test."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    _set_db(conn)
    await init_db(conn)
    yield conn
    await conn.close()
