"""Rate service: rate plans + per-night prices and restrictions.

Prices fall back to `unit_type.base_price` when a rate plan has no explicit
`price_day` row for a date. This keeps the partner cabinet usable before they
have set up full seasonal pricing.
"""

from __future__ import annotations

import datetime as dt

import asyncpg

from app.utils.logger import get_logger
from app.utils.redis import get_redis

log = get_logger(__name__)

PRICE_CACHE_TTL_SEC = 60
_PRICE_KEY = "prices:{rate_plan_id}:{from_iso}:{to_iso}"


async def create_rate_plan(
    conn: asyncpg.Connection,
    unit_type_id: str,
    name: str,
    cancellation_policy: str = "flexible",
) -> dict:
    row = await conn.fetchrow(
        """
        INSERT INTO rate_plan (unit_type_id, name, cancellation_policy)
        VALUES ($1, $2, $3)
        RETURNING id::text, unit_type_id::text, name, cancellation_policy, active
        """,
        unit_type_id,
        name,
        cancellation_policy,
    )
    assert row is not None
    return dict(row)


async def list_rate_plans(conn: asyncpg.Connection, unit_type_id: str) -> list[dict]:
    rows = await conn.fetch(
        "SELECT id::text, unit_type_id::text, name, cancellation_policy, active "
        "FROM rate_plan WHERE unit_type_id = $1 ORDER BY created_at",
        unit_type_id,
    )
    return [dict(r) for r in rows]


async def set_prices(
    conn: asyncpg.Connection,
    rate_plan_id: str,
    date_from: dt.date,
    date_to: dt.date,
    price: float,
    min_stay: int = 1,
) -> int:
    """Set the price for every night in [date_from, date_to).

    Existing rows are updated, missing ones created — so a partner can change
    a whole season in one call. Returns the number of affected nights.
    """
    if date_to <= date_from:
        raise ValueError("date_to must be after date_from")
    if price < 0:
        raise ValueError("price must be >= 0")
    if min_stay < 1:
        raise ValueError("min_stay must be >= 1")

    row = await conn.fetchrow(
        """
        WITH d AS (
            SELECT generate_series($1::date, ($2::date - interval '1 day')::date, '1 day')::date AS date
        )
        INSERT INTO price_day (rate_plan_id, date, price, min_stay)
        SELECT $3, d.date, $4, $5 FROM d
        ON CONFLICT (rate_plan_id, date) DO UPDATE
            SET price = EXCLUDED.price, min_stay = EXCLUDED.min_stay
        RETURNING 1
        """,
        date_from,
        date_to,
        rate_plan_id,
        price,
        min_stay,
    )
    assert row is not None
    await _invalidate(rate_plan_id)
    return 1


async def get_prices(
    conn: asyncpg.Connection,
    rate_plan_id: str,
    date_from: dt.date,
    date_to: dt.date,
) -> list[dict]:
    """Per-night prices over [date_from, date_to).

    Falls back to unit_type.base_price where no explicit price row exists.
    """
    if date_to <= date_from:
        raise ValueError("date_to must be after date_from")

    rows = await conn.fetch(
        """
        SELECT
            d.date,
            COALESCE(pd.price::float8, ut.base_price::float8) AS price,
            COALESCE(pd.min_stay, 1)                          AS min_stay,
            COALESCE(pd.max_stay, 0)                          AS max_stay,
            COALESCE(pd.cta, true)                            AS cta,
            COALESCE(pd.ctd, true)                            AS ctd,
            COALESCE(pd.stop_sell, false)                     AS stop_sell
        FROM generate_series($2::date, ($3::date - interval '1 day')::date, '1 day') AS d(date)
        LEFT JOIN price_day pd ON pd.rate_plan_id = $1 AND pd.date = d.date
        LEFT JOIN rate_plan  rp ON rp.id = $1
        LEFT JOIN unit_type  ut ON ut.id = rp.unit_type_id
        ORDER BY d.date
        """,
        rate_plan_id,
        date_from,
        date_to,
    )
    return [dict(r) for r in rows]


async def get_effective_price(conn: asyncpg.Connection, rate_plan_id: str, date: dt.date) -> float:
    """Single-night price with fallback, used by availability."""
    row = await conn.fetchrow(
        """
        SELECT COALESCE(pd.price::float8, ut.base_price::float8) AS price
        FROM rate_plan rp
        LEFT JOIN unit_type ut ON ut.id = rp.unit_type_id
        LEFT JOIN price_day pd ON pd.rate_plan_id = $1 AND pd.date = $2
        WHERE rp.id = $1
        """,
        rate_plan_id,
        date,
    )
    return float(row["price"]) if row else 0.0


async def _invalidate(rate_plan_id: str) -> None:
    try:
        redis = get_redis()
        async for key in redis.scan_iter(match=f"prices:{rate_plan_id}:*"):
            await redis.delete(key)
    except RuntimeError:
        pass  # Redis not initialised (unit tests)
    except Exception as exc:
        log.warning("price-cache-invalidate-failed", error=str(exc))
