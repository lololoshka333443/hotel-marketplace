"""Shared pytest fixtures.

DB-backed tests get a per-test connection inside a transaction that is always
rolled back, so tests never leave state behind.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio

from app.config.settings import settings
from app.db.pool import close_pool, init_pool


@pytest.fixture
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


@pytest_asyncio.fixture
async def app_pool() -> AsyncIterator[asyncpg.Pool]:
    """The real application pool, for tests that need concurrent connections.

    Used by the booking concurrency test: several connections must race on the
    same inventory rows to prove the FOR UPDATE lock works. Function-scoped so
    it shares the test's event loop.
    """
    pool = await init_pool()
    try:
        yield pool
    finally:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM booking_line")
                await conn.execute("DELETE FROM booking")
                await conn.execute("DELETE FROM inventory_day")
                await conn.execute("DELETE FROM unit_type")
                await conn.execute("DELETE FROM property")
                await conn.execute("DELETE FROM partner")
        await close_pool()
