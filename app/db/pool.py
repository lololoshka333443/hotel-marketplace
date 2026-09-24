"""asyncpg connection pool.

The booking core depends on explicit row locks, so all SQL is hand-written and
executed through this pool. No ORM — `FOR UPDATE` and `SERIALIZABLE` must stay
visible in code.

RLS note: on partner-scoped connections we set `app.partner_id` via
`server_settings` so Row Level Security policies can scope queries.
"""

from __future__ import annotations

import asyncpg
from asyncpg import Pool

from app.config.settings import settings

_pool: Pool | None = None


async def init_pool() -> Pool:
    """Create the global pool. Call once on startup."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=5,
            max_size=25,
            command_timeout=30,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> Pool:
    """Fast accessor. Pool must be initialised first (see init_pool)."""
    if _pool is None:
        raise RuntimeError("DB pool is not initialised. Call init_pool() on startup.")
    return _pool


async def acquire(partner_id: str | None = None):
    """Acquire a connection, optionally RLS-scoped to a partner.

    Usage:
        async with acquire(partner_id) as conn:
            await conn.execute("SELECT 1")
    """
    pool = get_pool()
    conn = await pool.acquire()
    try:
        if partner_id is not None:
            await conn.execute("SELECT set_config('app.partner_id', $1, true)", str(partner_id))
        yield conn
    finally:
        await pool.release(conn)
