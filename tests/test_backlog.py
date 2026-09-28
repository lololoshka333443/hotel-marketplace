"""Backlog limit for the outbox queue.

The worker drains the queue at `webhook_rate_per_sec` per subscription. A mass
operation (bulk price load, an iCal import of a whole season) can outpace it,
and then the events that cost money — bookings — sit behind events that do not.

The limit works two ways at once: bookings jump the backlog by priority, and
bulk events past the depth limit are shed rather than queued. Shedding is safe
because the channels it affects can pull rates and availability through the
read-API; a booking is never subject to it.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio

from app.config.settings import settings
from app.modules.auth import service as auth_service
from app.modules.auth.schemas import PartnerRegisterRequest
from app.modules.outbox import backlog
from app.modules.outbox import service as outbox_service
from app.modules.property import service as property_service
from app.modules.property.schemas import PropertyCreate


async def _seed(conn: asyncpg.Connection, email: str) -> dict:
    partner_id = str(
        await auth_service.register_partner(
            conn, PartnerRegisterRequest(email=email, password="secret123", name="Tester")
        )
    )
    prop = await property_service.create_property(
        conn,
        partner_id,
        PropertyCreate(
            name="Test",
            property_type="apartment",
            city="Koktebel",
            timezone="Europe/Simferopol",
        ),
    )
    row = await conn.fetchrow(
        "INSERT INTO unit_type (property_id, name, capacity, total_units, base_price) "
        "VALUES ($1, 'Студия', 2, 1, 3000) RETURNING id::text",
        prop.id,
    )
    assert row is not None
    return {"unit_type_id": row["id"], "partner_id": partner_id, "property_id": prop.id}


@pytest_asyncio.fixture
async def clean_outbox(committed_conn: asyncpg.Connection) -> AsyncIterator[None]:
    """A per-test outbox: no leftover events or shed counts from the last test.

    `committed_conn` clears the business tables but not the outbox internals,
    and these tests count exactly what they themselves shed. Explicitly ordered
    after it so the previous test's cleanup has already run.
    """
    await committed_conn.execute("DELETE FROM outbox_shed_counter; DELETE FROM outbox_event;")
    yield


async def _bulk_events(conn: asyncpg.Connection, n: int) -> None:
    """Stand up n pending bulk events, the way a price import would."""
    for i in range(n):
        await outbox_service.emit(
            conn,
            aggregate="inventory",
            aggregate_id=f"ut-{i}",
            event_type=outbox_service.INVENTORY_AVAILABILITY_CHANGED,
            payload={"i": i},
            property_id=None,
        )


@pytest.mark.asyncio
async def test_booking_emitted_when_the_queue_is_deep(committed_conn, clean_outbox) -> None:
    """A booking enters the queue at any depth — it is the source of truth."""
    await _bulk_events(committed_conn, 5)

    n_before = await backlog.depth(committed_conn)
    assert n_before == 5

    await outbox_service.emit(
        committed_conn,
        aggregate="booking",
        aggregate_id=str(uuid.uuid4()),
        event_type=outbox_service.BOOKING_CONFIRMED,
        payload={},
        property_id=None,
    )
    assert await backlog.depth(committed_conn) == 6


@pytest.mark.asyncio
async def test_bulk_shed_when_the_queue_is_over_the_limit(
    committed_conn, clean_outbox, monkeypatch
) -> None:
    """Past the limit, a bulk event is counted and dropped, not queued."""
    monkeypatch.setattr(settings, "outbox_max_pending", 3)
    await _bulk_events(committed_conn, 3)
    n_before = await backlog.depth(committed_conn)

    admitted = await backlog.admit(committed_conn, priority=backlog.PRIORITY_BULK, limit=n_before)
    assert admitted is False

    await outbox_service.emit(
        committed_conn,
        aggregate="inventory",
        aggregate_id="ut-shed",
        event_type=outbox_service.INVENTORY_AVAILABILITY_CHANGED,
        payload={},
        property_id=None,
    )

    # Nothing new in the queue; the drop is on the counter instead.
    assert await backlog.depth(committed_conn) == n_before
    row = await committed_conn.fetchrow(
        "SELECT n, last_shed_at FROM outbox_shed_counter WHERE aggregate = 'inventory'"
    )
    assert row is not None
    assert row["n"] == 1


@pytest.mark.asyncio
async def test_bulk_admitted_under_the_limit(committed_conn, clean_outbox) -> None:
    """Room left in the queue: the event is queued, the counter untouched."""
    await _bulk_events(committed_conn, 1)

    admitted = await backlog.admit(committed_conn, priority=backlog.PRIORITY_BULK, limit=10)
    assert admitted is True
    assert await backlog.shed_total(committed_conn) == 0


@pytest.mark.asyncio
async def test_booking_always_admitted_regardless_of_the_limit(
    committed_conn, clean_outbox
) -> None:
    """The limit gates bulk traffic only; a booking is never dropped."""
    admitted = await backlog.admit(committed_conn, priority=backlog.PRIORITY_BOOKING, limit=0)
    assert admitted is True


@pytest.mark.asyncio
async def test_booking_is_claimed_before_older_bulk(committed_conn, clean_outbox) -> None:
    """A booking jumps the backlog: claimed first even when it is the newest."""
    await _bulk_events(committed_conn, 3)
    # The booking arrives last but must leave first.
    booking_id = str(uuid.uuid4())
    await outbox_service.emit(
        committed_conn,
        aggregate="booking",
        aggregate_id=booking_id,
        event_type=outbox_service.BOOKING_CONFIRMED,
        payload={},
        property_id=None,
    )
    # Everything is due right now, so only priority decides the order.
    await committed_conn.execute(
        "UPDATE outbox_event SET next_attempt_at = now() WHERE status = 'pending'"
    )

    claimed = await outbox_service.claim_due(committed_conn, 10)

    assert len(claimed) == 4
    assert claimed[0]["aggregate_id"] == booking_id
    assert claimed[0]["aggregate"] == "booking"


@pytest.mark.asyncio
async def test_claim_still_ages_within_a_priority(committed_conn, clean_outbox) -> None:
    """Inside one priority class, the oldest event still goes first.

    A booking must not lose its place in line to another booking, and a bulk
    event must not cut in front of an older bulk one.
    """
    for i in range(3):
        await outbox_service.emit(
            committed_conn,
            aggregate="rate_plan",
            aggregate_id=f"rp-{i}",
            event_type=outbox_service.RATE_PRICES_CHANGED,
            payload={"i": i},
            property_id=None,
        )
        # Distinct happened_at, in the same order as the payload index.
        await committed_conn.execute(
            "UPDATE outbox_event SET happened_at = now() + ($1 || ' seconds')::interval "
            "WHERE aggregate_id = $2",
            str(i),
            f"rp-{i}",
        )
    await committed_conn.execute(
        "UPDATE outbox_event SET next_attempt_at = now() WHERE status = 'pending'"
    )

    claimed = await outbox_service.claim_due(committed_conn, 10)
    assert [c["aggregate_id"] for c in claimed] == ["rp-0", "rp-1", "rp-2"]


@pytest.mark.asyncio
async def test_shed_events_are_reported_in_metrics(
    committed_conn, clean_outbox, monkeypatch
) -> None:
    """The counter shows up where the staff can see it."""
    monkeypatch.setattr(settings, "outbox_max_pending", 2)
    await _bulk_events(committed_conn, 2)
    await outbox_service.emit(
        committed_conn,
        aggregate="inventory",
        aggregate_id="ut-shed",
        event_type=outbox_service.INVENTORY_AVAILABILITY_CHANGED,
        payload={},
        property_id=None,
    )

    metrics = await outbox_service.queue_metrics(committed_conn)
    assert metrics["shed_total"] == 1
    assert metrics["pending"] == 2


@pytest.mark.asyncio
async def test_shedding_does_not_break_the_emit(committed_conn, clean_outbox, monkeypatch) -> None:
    """A dropped event must never roll back the business transaction.

    The same guarantee the outbox always gave for a failing insert: the change
    the caller made stands even when the event does not enter the queue.
    """
    monkeypatch.setattr(settings, "outbox_max_pending", 3)
    await _bulk_events(committed_conn, 3)
    n_before = await backlog.depth(committed_conn)

    await outbox_service.emit(
        committed_conn,
        aggregate="inventory",
        aggregate_id="ut-shed",
        event_type=outbox_service.INVENTORY_AVAILABILITY_CHANGED,
        payload={},
        property_id=None,
    )

    assert await backlog.depth(committed_conn) == n_before
    assert await committed_conn.fetchval("SELECT count(*) FROM outbox_shed_counter") == 1
