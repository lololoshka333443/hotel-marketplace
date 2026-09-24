"""Shared pytest fixtures.

DB-backed tests get a per-test connection inside a transaction that is always
rolled back, so tests never leave state behind.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import asyncpg
import pytest_asyncio

from app.config.settings import settings


@pytest_asyncio.fixture
async def db_conn() -> AsyncIterator[asyncpg.Connection]:
    """Per-test connection inside a transaction that is always rolled back.

    Pool is created and closed per test. Cheap on local Postgres and avoids
    cross-event-loop issues in pytest-asyncio.
    """
    pool = await asyncpg.create_pool(dsn=settings.database_url, min_size=1, max_size=5)
    conn = await pool.acquire()
    tx = conn.transaction()
    await tx.start()
    try:
        yield conn
    finally:
        await tx.rollback()
        await pool.release(conn)
        await pool.close()
