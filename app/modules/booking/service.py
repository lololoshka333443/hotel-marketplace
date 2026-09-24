"""Booking service — the core of the platform.

Concurrency model: every hold is created inside a SERIALIZABLE transaction
that locks the affected `inventory_day` rows with `SELECT ... FOR UPDATE`,
ordered by (unit_type_id, date) to avoid deadlocks on overlapping ranges.
Two concurrent holds on the last room can never both succeed.

Idempotency: a client-supplied key makes retries safe — a replay returns the
original booking instead of creating a duplicate.
"""

from __future__ import annotations

import datetime as dt
import secrets

import asyncpg

from app.config import legal
from app.config.settings import settings
from app.utils.logger import get_logger

log = get_logger(__name__)

BOOKING_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _make_code() -> str:
    """Guest-facing code, e.g. BK-7K2Q9F."""
    body = "".join(secrets.choice(BOOKING_CODE_ALPHABET) for _ in range(6))
    return f"BK-{body}"


async def _load_or_lock_inventory(
    conn: asyncpg.Connection,
    unit_type_id: str,
    checkin: dt.date,
    checkout: dt.date,
) -> list[asyncpg.Record]:
    """Lock the inventory rows for the stay, ordered to avoid deadlocks.

    Returns the locked rows. Caller must be inside a transaction.
    """
    return await conn.fetch(
        """
        SELECT unit_type_id, date, available, hold, sold, closed
        FROM inventory_day
        WHERE unit_type_id = $1
          AND date >= $2
          AND date <  $3
        ORDER BY unit_type_id, date
        FOR UPDATE
        """,
        unit_type_id,
        checkin,
        checkout,
    )


class BookingError(Exception):
    """Base class for expected booking failures."""


class NotAvailable(BookingError):
    """No free inventory on the requested dates."""


class Conflict(BookingError):
    """Idempotency-key collision with a different payload."""


async def create_hold(
    conn: asyncpg.Connection,
    *,
    unit_type_id: str,
    checkin: dt.date,
    checkout: dt.date,
    guest_name: str,
    guest_email: str,
    guest_phone: str,
    idempotency_key: str | None = None,
) -> dict:
    """Reserve inventory for the stay and return the new hold booking.

    Raises NotAvailable when there is no free inventory, Conflict when the
    idempotency key is reused with different request data.

    The caller is responsible for the transaction; tests wrap this in a
    rolled-back transaction, the route wraps it in a committed one.
    """
    nights = (checkout - checkin).days
    if nights < 1:
        raise NotAvailable("checkout must be after checkin")

    # ---- idempotency: replay the exact same request if the key exists
    if idempotency_key:
        existing = await conn.fetchrow(
            """
            SELECT id::text, code, status, total_amount, hold_expires_at,
                   checkin_date, checkout_date, unit_type_id::text
            FROM booking WHERE idempotency_key = $1
            """,
            idempotency_key,
        )
        if existing is not None:
            same = (
                existing["unit_type_id"] == unit_type_id
                and existing["checkin_date"] == checkin
                and existing["checkout_date"] == checkout
            )
            if not same:
                raise Conflict("idempotency key used with different payload")
            log.info("hold-idempotent-replay", code=existing["code"])
            return dict(existing)

    # ---- unit type + price
    ut = await conn.fetchrow(
        "SELECT id::text, property_id::text, base_price, total_units FROM unit_type WHERE id = $1",
        unit_type_id,
    )
    if ut is None:
        raise NotAvailable("unit type not found")

    # ---- lock inventory rows, ordered by (unit_type_id, date)
    locked = await _load_or_lock_inventory(conn, unit_type_id, checkin, checkout)
    if len(locked) != nights:
        raise NotAvailable("inventory not generated for all nights of the stay")

    # ---- check availability on every night
    for row in locked:
        if row["closed"]:
            raise NotAvailable(f"dates closed (stop sell) at {row['date']}")
        free = row["available"] - row["hold"] - row["sold"]
        if free < 1:
            raise NotAvailable(f"no free inventory at {row['date']}")

    # ---- price
    total = float(ut["base_price"]) * nights
    commission = round(total * legal.COMMISSION_DEFAULT_RATE, 2)

    hold_expires_at = dt.datetime.now(dt.UTC) + dt.timedelta(minutes=settings.hold_ttl_min)
    code = _make_code()

    row = await conn.fetchrow(
        """
        INSERT INTO booking
            (code, idempotency_key, property_id, unit_type_id,
             guest_name, guest_email, guest_phone,
             checkin_date, checkout_date, status, origin,
             total_amount, commission_rate, commission_amt, hold_expires_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'hold', 'web',
                $10, $11, $12, $13)
        RETURNING id::text, code, status, total_amount, hold_expires_at
        """,
        code,
        idempotency_key,
        ut["property_id"],
        unit_type_id,
        guest_name,
        guest_email,
        guest_phone,
        checkin,
        checkout,
        total,
        legal.COMMISSION_DEFAULT_RATE,
        commission,
        hold_expires_at,
    )
    assert row is not None

    # ---- decrement availability (hold bucket) for each night
    await conn.executemany(
        """
        UPDATE inventory_day SET hold = hold + 1
        WHERE unit_type_id = $1 AND date = $2
        """,
        [(unit_type_id, r["date"]) for r in locked],
    )

    await conn.executemany(
        """
        INSERT INTO booking_line (booking_id, date, price)
        VALUES ($1, $2, $3)
        """,
        [(row["id"], r["date"], float(ut["base_price"])) for r in locked],
    )

    log.info(
        "hold-created",
        booking_id=row["id"],
        code=code,
        nights=nights,
        total=total,
        expires_at=hold_expires_at.isoformat(),
    )
    return dict(row)


async def release_hold(conn: asyncpg.Connection, booking_id: str) -> None:
    """Return hold inventory to the pool and mark the booking cancelled."""
    booking = await conn.fetchrow(
        "SELECT unit_type_id::text, checkin_date, checkout_date, status FROM booking WHERE id = $1",
        booking_id,
    )
    if booking is None:
        return
    if booking["status"] not in ("hold", "failed"):
        return

    await conn.executemany(
        """
        UPDATE inventory_day SET hold = GREATEST(hold - 1, 0)
        WHERE unit_type_id = $1
          AND date >= $2 AND date < $3
          AND hold > 0
        """,
        [(booking["unit_type_id"], booking["checkin_date"], booking["checkout_date"])],
    )
    await conn.execute(
        "UPDATE booking SET status = 'cancelled', cancelled_at = now() WHERE id = $1",
        booking_id,
    )
    log.info("hold-released", booking_id=booking_id)


async def expire_holds(conn: asyncpg.Connection) -> int:
    """Reaper: cancel holds whose TTL has passed. Returns count released."""
    rows = await conn.fetch(
        """
        SELECT id::text FROM booking
        WHERE status = 'hold' AND hold_expires_at < now()
        ORDER BY id
        FOR UPDATE SKIP LOCKED
        LIMIT 200
        """
    )
    released = 0
    for r in rows:
        async with conn.transaction():
            await release_hold(conn, r["id"])
        released += 1
    if released:
        log.info("reaper-expired-holds", count=released)
    return released
