"""Shared pytest fixtures.

Two DB fixtures:

- `db_conn`: connection inside a transaction that is always rolled back.
  Used by unit tests that must leave nothing behind.

- `committed_conn`: connection in autocommit mode with explicit cleanup.
  Used by tests whose code path opens its own transactions (payment service),
  which cannot nest inside an outer rollback.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import asyncpg
import pytest_asyncio

from app.config.settings import settings

_CLEANUP = (
    "DELETE FROM outbox_shed_counter; DELETE FROM webhook_delivery; "
    "DELETE FROM outbox_event; "
    "DELETE FROM webhook_subscription; "
    "DELETE FROM api_key; "
    "DELETE FROM ical_subscription; "
    "DELETE FROM booking_line; "
    "DELETE FROM payment; "
    "DELETE FROM booking; "
    "DELETE FROM inventory_day; "
    "DELETE FROM price_day; "
    "DELETE FROM rate_plan; "
    "DELETE FROM unit_type; "
    "DELETE FROM property; "
    "DELETE FROM partner; "
    "DELETE FROM admin;"
)


@pytest_asyncio.fixture
async def db_conn() -> AsyncIterator[asyncpg.Connection]:
    """Per-test connection, always rolled back."""
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
async def committed_conn() -> AsyncIterator[asyncpg.Connection]:
    """Per-test autocommit connection with explicit cleanup afterwards.

    For tests where the code under test manages its own transactions.
    """
    pool = await asyncpg.create_pool(dsn=settings.database_url, min_size=1, max_size=5)
    conn = await pool.acquire()
    try:
        yield conn
    finally:
        await conn.execute(_CLEANUP)
        await pool.release(conn)
        await pool.close()
