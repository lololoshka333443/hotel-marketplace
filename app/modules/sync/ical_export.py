"""iCal export - share a unit type's blocked calendar with any channel.

Pull-based and token-addressed: no login, the token in the URL IS the secret
(standard practice for calendar feeds). Channels poll the feed and map UID to
their listing; stable UIDs let them update and cancel cleanly.

Blocked dates are exactly what the partner sees on the chessboard:
  - confirmed stays (paid/confirmed)   -> STATUS:CONFIRMED
  - holds awaiting payment             -> STATUS:TENTATIVE
  - closed date ranges (stop sell)     -> STATUS:CONFIRMED
Free dates emit nothing, which is what channels expect.

DTEND is the checkout day and is exclusive: the stay covers [checkin, checkout),
matching inventory_day semantics. Only current/future stays are exported - past
events only pollute the feed.
"""

from __future__ import annotations

import datetime as dt
import secrets

import asyncpg

from app.utils.logger import get_logger

log = get_logger(__name__)

PRODID = "-//hotel-marketplace//ical-export//RU"

_STAY_STATUSES = ("hold", "paid", "confirmed")


def _escape(value: str) -> str:
    """RFC 5545 TEXT escaping."""
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")


def _date(value: dt.date) -> str:
    return value.strftime("%Y%m%d")


def _stamp() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")


def token() -> str:
    return secrets.token_urlsafe(24)


async def build_calendar(conn: asyncpg.Connection, unit_type_id: str) -> str | None:
    """Render the unit type's calendar as RFC 5545, or None if it doesn't exist."""
    name = await conn.fetchval("SELECT name FROM unit_type WHERE id = $1", unit_type_id)
    if name is None:
        return None

    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(name)}",
    ]

    # ---- stays: holds are tentative, paid/confirmed are firm
    stays = await conn.fetch(
        """
        SELECT id::text, code, guest_name, checkin_date, checkout_date, status
        FROM booking
        WHERE unit_type_id = $1
          AND status = ANY($2)
          AND checkout_date > CURRENT_DATE
        ORDER BY checkin_date
        """,
        unit_type_id,
        list(_STAY_STATUSES),
    )
    for stay in stays:
        status = "TENTATIVE" if stay["status"] == "hold" else "CONFIRMED"
        summary = f"Занято · {stay['code']}"
        lines += [
            "BEGIN:VEVENT",
            f"UID:booking:{stay['id']}",
            f"DTSTAMP:{_stamp()}",
            f"DTSTART;VALUE=DATE:{_date(stay['checkin_date'])}",
            f"DTEND;VALUE=DATE:{_date(stay['checkout_date'])}",
            f"SUMMARY:{_escape(summary)}",
            f"STATUS:{status}",
            "END:VEVENT",
        ]

    # ---- closed ranges (stop sell), contiguous runs collapsed into one event
    closed = await conn.fetch(
        """
        WITH closed_days AS (
            SELECT date,
                   date - (row_number() OVER (ORDER BY date)) * interval '1 day' AS grp
            FROM inventory_day
            WHERE unit_type_id = $1 AND closed AND date >= CURRENT_DATE
        )
        SELECT min(date)                    AS d_from,
               (max(date) + interval '1 day')::date AS d_to
        FROM closed_days
        GROUP BY grp
        ORDER BY d_from
        """,
        unit_type_id,
    )
    for run in closed:
        lines += [
            "BEGIN:VEVENT",
            f"UID:closed:{unit_type_id}:{run['d_from']}",
            f"DTSTAMP:{_stamp()}",
            f"DTSTART;VALUE=DATE:{_date(run['d_from'])}",
            f"DTEND;VALUE=DATE:{_date(run['d_to'])}",
            "SUMMARY:Закрыто для бронирования",
            "STATUS:CONFIRMED",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


async def get_feed_by_token(conn: asyncpg.Connection, feed_token: str) -> dict | None:
    row = await conn.fetchrow(
        """
        SELECT f.unit_type_id::text AS unit_type_id, f.enabled
        FROM ical_feed f
        WHERE f.token = $1
        """,
        feed_token,
    )
    return dict(row) if row else None


async def get_feed_for_unit_type(
    conn: asyncpg.Connection, unit_type_id: str, partner_id: str
) -> dict | None:
    """Current feed, but only for a unit type the partner owns."""
    row = await conn.fetchrow(
        """
        SELECT f.id::text AS id, f.token, f.enabled, f.created_at
        FROM ical_feed f
        JOIN unit_type ut ON ut.id = f.unit_type_id
        JOIN property  p  ON p.id = ut.property_id
        WHERE f.unit_type_id = $1 AND p.partner_id = $2
        """,
        unit_type_id,
        partner_id,
    )
    return dict(row) if row else None


async def create_or_rotate_feed(
    conn: asyncpg.Connection, unit_type_id: str, partner_id: str
) -> dict:
    """Create the feed or rotate its token. Partner must own the unit type."""
    owned = await conn.fetchval(
        """
        SELECT 1 FROM unit_type ut
        JOIN property p ON p.id = ut.property_id
        WHERE ut.id = $1 AND p.partner_id = $2
        """,
        unit_type_id,
        partner_id,
    )
    if not owned:
        raise ValueError("unit type not found")

    row = await conn.fetchrow(
        """
        INSERT INTO ical_feed (unit_type_id, token)
        VALUES ($1, $2)
        ON CONFLICT (unit_type_id) DO UPDATE
            SET token = EXCLUDED.token, enabled = true
        RETURNING id::text, token, enabled, created_at
        """,
        unit_type_id,
        token(),
    )
    assert row is not None
    log.info("ical-feed-rotated", unit_type_id=unit_type_id)
    return dict(row)
