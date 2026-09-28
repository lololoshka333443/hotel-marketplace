"""Backlog limit for the outbox queue.

The worker drains the queue at `webhook_rate_per_sec` *per subscription*. A mass
operation — a bulk price load, an iCal import of a whole season — can throw
thousands of events at it at once, and those events sit in front of a booking
while the partner's channel learns about the booking late. The one event type
that costs money gets pushed behind the one that does not.

So the queue is bounded deliberately, not accidentally:

* priority — `booking.*` is high and everything else is low; `claim_due` takes
  the highest-priority due rows first, so a booking jumps the whole backlog.
* shedding — once the queue is deeper than `outbox_max_pending`, a low-priority
  event is not emitted at all. The channels it was meant for can pull current
  rates and availability through the channel read-API and iCal, so a dropped
  notification heals on the next pull instead of being remembered by a queue.

A booking is never shed and never waits behind bulk events: the booking is the
source of truth, and the whole point of the outbox is to tell a channel about
it. Whatever the queue looks like, the money goes first.
"""

from __future__ import annotations

import asyncpg

from app.utils.logger import get_logger

log = get_logger(__name__)

# Priority levels. Low number wins, so a booking is claimed first at every
# depth. Bookings are also the only events exempt from shedding.
PRIORITY_BOOKING = 1
PRIORITY_BULK = 9


async def depth(conn: asyncpg.Connection) -> int:
    """Everything the worker still owes a subscriber.

    'delivering' counts too: a claimed batch is one network round-trip away from
    leaving, so it still occupies the subscriber's rate budget.
    """
    return await conn.fetchval(
        "SELECT count(*) FROM outbox_event WHERE status IN ('pending','delivering')"
    )


async def admit(conn: asyncpg.Connection, *, priority: int, limit: int) -> bool:
    """Should this event enter the queue?

    A booking always enters, at any depth — it is the source of truth, so it is
    never dropped and never made to wait. Anything else enters while there is
    still room; past the limit it is shed, because the channel can recover the
    same fact by pulling rates and availability through the read-API.
    """
    if priority == PRIORITY_BOOKING:
        return True
    return await depth(conn) < limit


async def count_shed(conn: asyncpg.Connection, *, aggregate: str, event_type: str) -> None:
    """Record that one event was dropped, so the staff can see the rate.

    One row per (aggregate, event_type) — a counter, not a second queue. It is
    a gauge for the admin strip, never something to drain.
    """
    await conn.execute(
        """
        INSERT INTO outbox_shed_counter (aggregate, event_type, n)
        VALUES ($1, $2, 1)
        ON CONFLICT (aggregate, event_type) DO UPDATE
            SET n = outbox_shed_counter.n + 1,
                last_shed_at = now()
        """,
        aggregate,
        event_type,
    )


async def shed_total(conn: asyncpg.Connection) -> int:
    """How many events the limit has dropped since the counter began."""
    return await conn.fetchval("SELECT coalesce(sum(n), 0)::int FROM outbox_shed_counter")
