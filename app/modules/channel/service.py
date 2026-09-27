"""Channel write-API.

A channel pushes bookings into us with an API key instead of a JWT. The key
resolves to a partner, and the booking goes through the *same* path a guest
uses: create_hold under SERIALIZABLE row locks, then pay_and_confirm. A channel
can never bypass the double-booking invariant or invent inventory it does not
own.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import secrets

import asyncpg

from app.utils.logger import get_logger

log = get_logger(__name__)

KEY_PREFIX = "hm_live_"
KEY_BYTES = 32
# Visible fingerprint in the UI: "hm_live_3f9a2b".
PREFIX_LEN = len(KEY_PREFIX) + 6


class ChannelError(Exception):
    """Base class for expected channel-API failures."""


class KeyRejected(ChannelError):
    """Unknown, disabled or malformed API key."""


class NotOwned(ChannelError):
    """The unit type or booking belongs to another partner."""


class NotAvailable(ChannelError):
    """The booking cannot move the way the caller asked."""


def _hash(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_key() -> str:
    """A new plaintext key. Only ever returned to the partner once."""
    return f"{KEY_PREFIX}{secrets.token_urlsafe(KEY_BYTES)}"


def is_well_formed(raw_key: str) -> bool:
    return raw_key.startswith(KEY_PREFIX) and len(raw_key) > PREFIX_LEN


async def create_key(
    conn: asyncpg.Connection, partner_id: str, label: str
) -> dict:
    """Create a key. The plaintext is in the response and nowhere else."""
    raw = generate_key()
    row = await conn.fetchrow(
        """
        INSERT INTO api_key (partner_id, label, key_hash, key_prefix)
        VALUES ($1, $2, $3, $4)
        RETURNING id::text, label, key_prefix, enabled, last_used_at, created_at
        """,
        partner_id,
        label,
        _hash(raw),
        raw[:PREFIX_LEN],
    )
    assert row is not None
    log.info("api-key-created", partner_id=partner_id, label=label)
    return {**dict(row), "key": raw}


async def list_keys(conn: asyncpg.Connection, partner_id: str) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT id::text, label, key_prefix, enabled, last_used_at, created_at
        FROM api_key
        WHERE partner_id = $1
        ORDER BY created_at DESC
        """,
        partner_id,
    )
    return [dict(r) for r in rows]


async def revoke_key(conn: asyncpg.Connection, partner_id: str, key_id: str) -> bool:
    """Revoke. Ownership is checked in the same statement, never trust the id."""
    result = await conn.execute(
        "DELETE FROM api_key WHERE id = $1 AND partner_id = $2",
        key_id,
        partner_id,
    )
    return result.endswith(" 1")


async def resolve_key(conn: asyncpg.Connection, raw_key: str) -> dict:
    """Map a presented key to its partner. Raises KeyRejected if unusable.

    last_used_at is stamped on every use so the partner can spot a stale or
    leaked key; a failed lookup is not recorded.
    """
    if not is_well_formed(raw_key):
        raise KeyRejected("malformed api key")

    row = await conn.fetchrow(
        """
        SELECT k.id::text, k.partner_id::text, k.label, k.enabled, p.status
        FROM api_key k
        JOIN partner p ON p.id = k.partner_id
        WHERE k.key_hash = $1
        """,
        _hash(raw_key),
    )
    if row is None or not row["enabled"]:
        raise KeyRejected("api key not found")
    if row["status"] != "active":
        raise KeyRejected("partner account is not active")

    await conn.execute(
        "UPDATE api_key SET last_used_at = now() WHERE id = $1", row["id"]
    )
    return dict(row)


async def unit_type_owned_by(
    conn: asyncpg.Connection, unit_type_id: str, partner_id: str
) -> bool:
    return bool(
        await conn.fetchval(
            """
            SELECT 1 FROM unit_type ut
            JOIN property p ON p.id = ut.property_id
            WHERE ut.id = $1 AND p.partner_id = $2
            """,
            unit_type_id,
            partner_id,
        )
    )


async def booking_owned_by(
    conn: asyncpg.Connection, booking_id: str, partner_id: str
) -> bool:
    """A channel may only see bookings on its own inventory."""
    return bool(
        await conn.fetchval(
            """
            SELECT 1 FROM booking b
            JOIN property p ON p.id = b.property_id
            WHERE b.id = $1 AND p.partner_id = $2 AND b.origin = 'channel'
            """,
            booking_id,
            partner_id,
        )
    )


def idempotency_namespace(partner_id: str, client_key: str) -> str:
    """Channel idempotency keys live in their own space.

    A channel's keys never collide with web idempotency keys or with another
    channel's, so a replay is always the same booking.
    """
    return f"channel:{partner_id}:{client_key}"


async def create_channel_booking(
    conn: asyncpg.Connection,
    *,
    partner_id: str,
    unit_type_id: str,
    checkin: dt.date,
    checkout: dt.date,
    guest_name: str,
    guest_email: str,
    guest_phone: str,
    client_key: str,
) -> dict:
    """The channel write path: the same route a guest takes, origin 'channel'.

    Hold under the SERIALIZABLE inventory locks, then confirm through the
    payment provider. A replay of the same idempotency key replays the original
    booking and is still a success.

    Raises NotOwned / NotAvailable / Conflict / PaymentError.
    """
    from app.modules.booking import service as booking_service
    from app.modules.payment import service as payment_service

    if not await unit_type_owned_by(conn, unit_type_id, partner_id):
        raise NotOwned("unit type not found")

    idem = idempotency_namespace(partner_id, client_key)

    # 1. Hold with the same row locks a guest hold takes.
    async with conn.transaction(isolation="serializable"):
        hold = await booking_service.create_hold(
            conn,
            unit_type_id=unit_type_id,
            checkin=checkin,
            checkout=checkout,
            guest_name=guest_name,
            guest_email=guest_email,
            guest_phone=guest_phone,
            idempotency_key=idem,
            origin="channel",
        )

    # A replay of an already-confirmed booking is a success, not an error:
    # the channel retried after we already confirmed.
    if hold["status"] == "confirmed":
        return booking_out(hold)

    # 2. The channel vouches for the payment; confirm exactly like the web
    #    checkout does. The hold bucket becomes sold.
    confirmed = await payment_service.pay_and_confirm(hold["id"], conn=conn)
    log.info(
        "channel-booking-created",
        booking_id=confirmed["id"],
        code=confirmed["code"],
        partner_id=partner_id,
    )
    return confirmed


async def cancel_channel_booking(
    conn: asyncpg.Connection, partner_id: str, booking_id: str
) -> dict:
    """Cancel a channel booking: a hold is released, a confirmed one refunded.

    Only channel-origin bookings on this partner's inventory are reachable.
    """
    from app.modules.booking import service as booking_service
    from app.modules.payment import service as payment_service

    if not await booking_owned_by(conn, booking_id, partner_id):
        raise NotOwned("booking not found")

    status_now = await conn.fetchval(
        "SELECT status FROM booking WHERE id = $1", booking_id
    )
    if status_now is None:
        raise NotOwned("booking not found")

    if status_now == "confirmed":
        return await payment_service.refund_booking(booking_id, conn=conn)
    if status_now == "hold":
        async with conn.transaction(isolation="serializable"):
            await booking_service.release_hold(conn, booking_id)
        return {"id": booking_id, "status": "cancelled"}
    raise NotAvailable(f"cannot cancel booking with status={status_now}")


def booking_out(row) -> dict:
    """Shape a booking row the way the channel API returns it."""
    return {
        "id": row["id"],
        "code": row["code"],
        "status": row["status"],
        "total_amount": float(row["total_amount"]),
        "checkin_date": row["checkin_date"].isoformat(),
        "checkout_date": row["checkout_date"].isoformat(),
    }
