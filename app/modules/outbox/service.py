"""Outbox: write an event in the same transaction as the change it describes.

The API is deliberately tiny — `emit()` at the call site, nothing else — so
that adding an event to a service is a one-liner inside its transaction. A
background worker (worker.py) owns the delivery half.

Ownership: every event carries the property it is about, so the worker can
match it to a partner's subscription without joining business tables at
delivery time.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg

from app.utils.logger import get_logger

log = get_logger(__name__)

# Event types. A subscription lists the ones it wants, or '*' for all.
BOOKING_CONFIRMED = "booking.confirmed"
BOOKING_CANCELLED = "booking.cancelled"
RATE_PRICES_CHANGED = "rate.prices_changed"
INVENTORY_AVAILABILITY_CHANGED = "inventory.availability_changed"
PROPERTY_STATUS_CHANGED = "property.status_changed"

ALL_EVENT_TYPES = (
    BOOKING_CONFIRMED,
    BOOKING_CANCELLED,
    RATE_PRICES_CHANGED,
    INVENTORY_AVAILABILITY_CHANGED,
    PROPERTY_STATUS_CHANGED,
)


async def emit(
    conn: asyncpg.Connection,
    *,
    aggregate: str,
    aggregate_id: str,
    event_type: str,
    payload: dict[str, Any],
    property_id: str,
) -> None:
    """Append an outbox row. Caller must be inside the business transaction.

    A failure here must not break the business operation: the event is
    best-effort, the booking is the source of truth.
    """
    try:
        await conn.execute(
            """
            INSERT INTO outbox_event (aggregate, aggregate_id, event_type, payload, property_id)
            VALUES ($1, $2, $3, $4, $5)
            """,
            aggregate,
            aggregate_id,
            event_type,
            json.dumps(payload, default=str),
            property_id,
        )
    except Exception as exc:
        # Never let a logging failure roll back a booking.
        log.warning("outbox-emit-failed", event_type=event_type, error=str(exc))


async def property_of_unit_type(conn: asyncpg.Connection, unit_type_id: str) -> str | None:
    return await conn.fetchval(
        "SELECT property_id::text FROM unit_type WHERE id = $1", unit_type_id
    )


async def property_of_rate_plan(conn: asyncpg.Connection, rate_plan_id: str) -> str | None:
    return await conn.fetchval(
        "SELECT ut.property_id::text FROM rate_plan rp "
        "JOIN unit_type ut ON ut.id = rp.unit_type_id "
        "WHERE rp.id = $1",
        rate_plan_id,
    )


# ---- worker-facing half ----------------------------------------------------


async def claim_due(conn: asyncpg.Connection, limit: int = 50) -> list[dict]:
    """Claim pending events for delivery.

    Claims by flipping status to 'delivering' in the same statement, exactly
    like the iCal importer's list_due: no lock is held across the network calls
    that follow. If this process dies, the reclaim loop puts the rows back.
    """
    rows = await conn.fetch(
        """
        WITH due AS (
            SELECT id FROM outbox_event
            WHERE status = 'pending' AND next_attempt_at <= now()
            ORDER BY happened_at
            LIMIT $1
            FOR UPDATE SKIP LOCKED
        )
        UPDATE outbox_event
        SET status = 'delivering', claimed_at = now()
        WHERE id IN (SELECT id FROM due)
        RETURNING id::text, aggregate, aggregate_id, event_type, payload,
                  attempts, max_attempts, property_id::text, happened_at
        """,
        limit,
    )
    out = []
    for r in rows:
        event = dict(r)
        # asyncpg returns jsonb as text; deliver it as a real object.
        if isinstance(event["payload"], str):
            event["payload"] = json.loads(event["payload"])
        out.append(event)
    return out


async def reclaim_stale(conn: asyncpg.Connection, timeout_sec: int = 300) -> int:
    """Return rows a dead worker left in 'delivering' back to the queue."""
    result = await conn.execute(
        """
        UPDATE outbox_event
        SET status = 'pending', claimed_at = NULL
        WHERE status = 'delivering' AND claimed_at < now() - ($1 || ' seconds')::interval
        """,
        str(timeout_sec),
    )
    n = int(result.split()[-1]) if result.startswith("UPDATE") else 0
    if n:
        log.info("outbox-reclaimed", count=n)
    return n


async def mark_published(conn: asyncpg.Connection, event_id: str) -> None:
    await conn.execute(
        """
        UPDATE outbox_event
        SET status = 'published', published_at = now(), last_error = NULL
        WHERE id = $1
        """,
        event_id,
    )


async def mark_retry(
    conn: asyncpg.Connection, event_id: str, attempts: int, error: str
) -> None:
    """Schedule the next attempt with exponential backoff, or dead-letter."""
    row = await conn.fetchrow(
        """
        UPDATE outbox_event
        SET attempts = $2,
            status = CASE WHEN $2 >= max_attempts THEN 'failed' ELSE 'pending' END,
            next_attempt_at = CASE
                WHEN $2 >= max_attempts THEN next_attempt_at
                ELSE now() + (least($2, 8) ^ 2 || ' seconds')::interval
            END,
            last_error = left($3, 500)
        WHERE id = $1
        RETURNING status
        """,
        event_id,
        attempts,
        error,
    )
    if row is not None and row["status"] == "failed":
        log.warning("outbox-dead-lettered", event_id=event_id, attempts=attempts)


async def record_delivery(
    conn: asyncpg.Connection,
    event_id: str,
    subscription_id: str,
    ok: bool,
    status_code: int | None,
    error: str | None,
) -> None:
    """Upsert the per-subscription delivery log."""
    await conn.execute(
        """
        INSERT INTO webhook_delivery (event_id, subscription_id, status, status_code, error)
        VALUES ($1, $2, $3, $4, left($5, 500))
        ON CONFLICT (event_id, subscription_id) DO UPDATE
            SET status = EXCLUDED.status,
                status_code = EXCLUDED.status_code,
                error = EXCLUDED.error,
                delivered_at = now()
        """,
        event_id,
        subscription_id,
        "success" if ok else "failed",
        status_code,
        error,
    )
    await conn.execute(
        """
        UPDATE webhook_subscription
        SET last_delivery_at = now(),
            last_status = $2,
            last_error = CASE WHEN $2 = 'success' THEN NULL ELSE left($3, 500) END
        WHERE id = $1
        """,
        subscription_id,
        "success" if ok else "failed",
        error,
    )


async def subscribers_for(
    conn: asyncpg.Connection, event_id: str, event_type: str
) -> list[dict]:
    """Subscriptions that still need this event.

    Joins the event's property to its owner's subscriptions, keeps the ones
    subscribed to this event type, and drops any that already answered 2xx —
    so a retry after a partial failure only reaches what it did not reach.
    """
    rows = await conn.fetch(
        """
        SELECT s.id::text, s.url, s.secret
        FROM outbox_event e
        JOIN property p ON p.id = e.property_id
        JOIN webhook_subscription s ON s.partner_id = p.partner_id
        WHERE e.id = $1
          AND s.enabled
          AND ('*' = ANY (s.event_types) OR $2 = ANY (s.event_types))
          AND NOT EXISTS (
              SELECT 1 FROM webhook_delivery d
              WHERE d.event_id = e.id AND d.subscription_id = s.id AND d.status = 'success'
          )
        """,
        event_id,
        event_type,
    )
    return [dict(r) for r in rows]
