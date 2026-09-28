"""Reconciliation tests: channel bookings vs what their webhook got.

The report answers one question — "the partner says they never got this
booking, is that on us?" — for every booking pushed in through the channel
API, by looking at the delivery of its latest booking event.

States a booking can be in:
  delivered     every webhook that wanted the event answered 2xx
  queued        the event is still in flight
  failed        the event dead-lettered
  undelivered   a webhook wanted it and none succeeded
  partial       some of the wanting webhooks succeeded
  no_listener   no webhook is listening (not an error — the partner's hook is
                off, or they never set one up)
"""

from __future__ import annotations

import datetime as dt
import uuid

import asyncpg
import pytest

from app.modules.auth import service as auth_service
from app.modules.auth.schemas import PartnerRegisterRequest
from app.modules.channel import service as channel_service
from app.modules.outbox import service as outbox_service
from app.modules.property import service as property_service
from app.modules.property.schemas import PropertyCreate

TODAY = dt.date.today()


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
    await conn.execute(
        "INSERT INTO inventory_day (unit_type_id, date, available) "
        "SELECT $1, d.date, 1 FROM generate_series("
        "  (CURRENT_DATE - interval '7 days')::date,"
        "  (CURRENT_DATE + interval '89 days')::date, '1 day'"
        ") AS d(date)",
        row["id"],
    )
    return {"unit_type_id": row["id"], "partner_id": partner_id, "property_id": prop.id}


def _push(seed: dict, *, day: int = 10) -> dict:
    return dict(
        partner_id=seed["partner_id"],
        unit_type_id=seed["unit_type_id"],
        checkin=TODAY + dt.timedelta(days=day),
        checkout=TODAY + dt.timedelta(days=day + 1),
        guest_name="Иван Гость",
        guest_email=f"g{uuid.uuid4().hex[:6]}@example.com",
        guest_phone="+79991234567",
        client_key=f"rec-{uuid.uuid4()}",
    )


async def _subscribe(conn: asyncpg.Connection, partner_id: str, *, enabled: bool = True) -> str:
    return await conn.fetchval(
        """
        INSERT INTO webhook_subscription (partner_id, url, secret, event_types, enabled)
        VALUES ($1, 'http://localhost:9/hooks', 'rec-secret-rec', '{*}', $2)
        RETURNING id::text
        """,
        partner_id,
        enabled,
    )


async def _deliver_once(conn: asyncpg.Connection, event_id: str, subscription_id: str) -> None:
    """Record a successful delivery the way the worker would."""
    await outbox_service.record_delivery(conn, event_id, subscription_id, True, 200, None)


@pytest.mark.asyncio
async def test_confirmed_booking_with_live_hook_is_delivered(committed_conn) -> None:
    seed = await _seed(committed_conn, "rec1@example.com")
    sub_id = await _subscribe(committed_conn, seed["partner_id"])

    booking = await channel_service.create_channel_booking(committed_conn, **_push(seed))
    event_id = await committed_conn.fetchval(
        """
        SELECT id::text FROM outbox_event
        WHERE aggregate = 'booking' AND aggregate_id = $1
        ORDER BY happened_at DESC LIMIT 1
        """,
        booking["id"],
    )
    assert event_id is not None
    await outbox_service.mark_published(committed_conn, event_id)
    await _deliver_once(committed_conn, event_id, sub_id)

    report = await outbox_service.reconciliation(committed_conn)
    assert report["summary"]["total"] == 1
    assert report["summary"]["delivered"] == 1

    row = report["bookings"][0]
    assert row["booking_id"] == booking["id"]
    assert row["delivery_status"] == "delivered"
    assert row["event"]["expected_subscribers"] == 1
    assert row["event"]["delivered_ok"] == 1


@pytest.mark.asyncio
async def test_no_hook_at_all_is_not_an_error(committed_conn) -> None:
    """A partner without a webhook subscription is a 'no_listener', not a failure."""
    seed = await _seed(committed_conn, "rec2@example.com")
    booking = await channel_service.create_channel_booking(committed_conn, **_push(seed))

    report = await outbox_service.reconciliation(committed_conn)
    row = report["bookings"][0]
    assert row["booking_id"] == booking["id"]
    assert row["delivery_status"] == "no_listener"
    assert report["summary"]["no_listener"] == 1
    assert report["summary"]["delivered"] == 0


@pytest.mark.asyncio
async def test_disabled_hook_is_no_listener(committed_conn) -> None:
    seed = await _seed(committed_conn, "rec3@example.com")
    await _subscribe(committed_conn, seed["partner_id"], enabled=False)
    await channel_service.create_channel_booking(committed_conn, **_push(seed))

    report = await outbox_service.reconciliation(committed_conn)
    assert report["bookings"][0]["delivery_status"] == "no_listener"


@pytest.mark.asyncio
async def test_dead_lettered_event_is_failed(committed_conn) -> None:
    seed = await _seed(committed_conn, "rec4@example.com")
    await _subscribe(committed_conn, seed["partner_id"])
    booking = await channel_service.create_channel_booking(committed_conn, **_push(seed))

    # The worker gave up on this event.
    await committed_conn.execute(
        """
        UPDATE outbox_event
        SET status = 'failed', last_error = '6 attempts: connection refused'
        WHERE aggregate_id = $1
        """,
        booking["id"],
    )

    report = await outbox_service.reconciliation(committed_conn)
    row = report["bookings"][0]
    assert row["delivery_status"] == "failed"
    assert row["event"]["last_error"] == "6 attempts: connection refused"
    assert report["summary"]["failed"] == 1


@pytest.mark.asyncio
async def test_queued_event_is_in_flight(committed_conn) -> None:
    seed = await _seed(committed_conn, "rec5@example.com")
    await _subscribe(committed_conn, seed["partner_id"])
    await channel_service.create_channel_booking(committed_conn, **_push(seed))
    # The event is claimed but not yet answered.
    events = await outbox_service.claim_due(committed_conn)

    report = await outbox_service.reconciliation(committed_conn)
    assert report["bookings"][0]["delivery_status"] == "queued"
    assert len(events) == 1


@pytest.mark.asyncio
async def test_published_but_never_delivered_is_undelivered(committed_conn) -> None:
    """An event marked published with no successful delivery on record."""
    seed = await _seed(committed_conn, "rec6@example.com")
    await _subscribe(committed_conn, seed["partner_id"])
    booking = await channel_service.create_channel_booking(committed_conn, **_push(seed))
    await committed_conn.execute(
        """
        UPDATE outbox_event SET status = 'published'
        WHERE aggregate_id = $1
        """,
        booking["id"],
    )

    report = await outbox_service.reconciliation(committed_conn)
    row = report["bookings"][0]
    assert row["delivery_status"] == "undelivered"
    assert row["event"]["expected_subscribers"] == 1
    assert row["event"]["delivered_ok"] == 0


@pytest.mark.asyncio
async def test_partial_when_the_ledger_is_incomplete(committed_conn) -> None:
    """Delivered to both hooks, but one delivery row is gone (retention pruned it).

    The event did go out, yet the ledger no longer proves it for every
    subscriber: that is a partial, and the staff can see which one is missing.
    """
    seed = await _seed(committed_conn, "rec7@example.com")
    ok_sub = await _subscribe(committed_conn, seed["partner_id"])
    other_sub = await _subscribe(committed_conn, seed["partner_id"])
    booking = await channel_service.create_channel_booking(committed_conn, **_push(seed))

    event_id = await committed_conn.fetchval(
        "SELECT id::text FROM outbox_event WHERE aggregate_id = $1 ORDER BY happened_at DESC LIMIT 1",
        booking["id"],
    )
    await _deliver_once(committed_conn, event_id, ok_sub)
    await _deliver_once(committed_conn, event_id, other_sub)
    await outbox_service.mark_published(committed_conn, event_id)
    # Retention drops one delivery row.
    await committed_conn.execute(
        "DELETE FROM webhook_delivery WHERE subscription_id = $1", other_sub
    )

    report = await outbox_service.reconciliation(committed_conn)
    row = report["bookings"][0]
    assert row["event"]["expected_subscribers"] == 2
    assert row["event"]["delivered_ok"] == 1
    assert row["delivery_status"] == "partial"
    assert report["summary"]["partial"] == 1


@pytest.mark.asyncio
async def test_cancellation_supersedes_confirmation(committed_conn) -> None:
    """The latest booking event wins: a cancelled booking is judged by its cancellation."""
    seed = await _seed(committed_conn, "rec8@example.com")
    sub_id = await _subscribe(committed_conn, seed["partner_id"])
    booking = await channel_service.create_channel_booking(committed_conn, **_push(seed))

    confirmed_id = await committed_conn.fetchval(
        "SELECT id::text FROM outbox_event WHERE aggregate_id = $1 ORDER BY happened_at DESC LIMIT 1",
        booking["id"],
    )
    await _deliver_once(committed_conn, confirmed_id, sub_id)

    cancelled = await channel_service.cancel_channel_booking(
        committed_conn, seed["partner_id"], booking["id"]
    )
    assert cancelled["status"] == "refunded"

    cancelled_id = await committed_conn.fetchval(
        "SELECT id::text FROM outbox_event WHERE aggregate_id = $1 ORDER BY happened_at DESC LIMIT 1",
        booking["id"],
    )
    assert cancelled_id != confirmed_id
    await outbox_service.mark_published(committed_conn, cancelled_id)
    await _deliver_once(committed_conn, cancelled_id, sub_id)

    report = await outbox_service.reconciliation(committed_conn)
    row = report["bookings"][0]
    assert row["event"]["event_type"] == outbox_service.BOOKING_CANCELLED
    assert row["delivery_status"] == "delivered"


@pytest.mark.asyncio
async def test_date_range_filters_and_web_bookings_excluded(committed_conn) -> None:
    """Only channel bookings in the range show up; a web booking never does."""
    from app.modules.booking import service as booking_service

    seed = await _seed(committed_conn, "rec9@example.com")
    inside = await channel_service.create_channel_booking(committed_conn, **_push(seed, day=10))
    outside = await channel_service.create_channel_booking(committed_conn, **_push(seed, day=40))
    # The range filters on when the push happened, not the stay dates.
    await committed_conn.execute(
        "UPDATE booking SET created_at = $2 WHERE id = $1",
        outside["id"],
        TODAY - dt.timedelta(days=90),
    )

    # A booking the guest made directly: not the channel's business.
    async with committed_conn.transaction(isolation="serializable"):
        await booking_service.create_hold(
            committed_conn,
            unit_type_id=seed["unit_type_id"],
            checkin=TODAY + dt.timedelta(days=12),
            checkout=TODAY + dt.timedelta(days=13),
            guest_name="Гость",
            guest_email="w@example.com",
            guest_phone="+79991112233",
            idempotency_key=f"w-{uuid.uuid4()}",
        )

    all_report = await outbox_service.reconciliation(committed_conn)
    assert all_report["summary"]["total"] == 2

    narrow = await outbox_service.reconciliation(
        committed_conn, TODAY, TODAY + dt.timedelta(days=20)
    )
    assert narrow["summary"]["total"] == 1
    assert narrow["bookings"][0]["booking_id"] == inside["id"]
    assert narrow["date_from"] == TODAY.isoformat()
    assert narrow["date_to"] == (TODAY + dt.timedelta(days=20)).isoformat()


@pytest.mark.asyncio
async def test_delivered_verdict_is_not_blocked_by_a_late_hook(committed_conn) -> None:
    """Every expected hook answered, but the event still retries a later one.

    A subscription created after the event fired is not 'expected': it may
    keep failing and keep the event queued, but the booking is delivered as
    far as the channels that matter are concerned.
    """
    seed = await _seed(committed_conn, "rec11@example.com")
    expected_sub = await _subscribe(committed_conn, seed["partner_id"])
    booking = await channel_service.create_channel_booking(committed_conn, **_push(seed))

    event_id = await committed_conn.fetchval(
        "SELECT id::text FROM outbox_event WHERE aggregate_id = $1 ORDER BY happened_at DESC LIMIT 1",
        booking["id"],
    )
    await _deliver_once(committed_conn, event_id, expected_sub)
    # A second hook appears later and keeps failing: the event stays pending.
    late_sub = await _subscribe(committed_conn, seed["partner_id"])
    await outbox_service.record_delivery(committed_conn, event_id, late_sub, False, 502, "HTTP 502")

    report = await outbox_service.reconciliation(committed_conn)
    row = report["bookings"][0]
    assert row["event"]["expected_subscribers"] == 1
    assert row["event"]["delivered_ok"] == 1
    assert row["delivery_status"] == "delivered"


@pytest.mark.asyncio
async def test_hook_created_after_the_event_is_not_blamed(committed_conn) -> None:
    """A subscription that did not exist when the event fired cannot be expected to have it."""
    seed = await _seed(committed_conn, "rec10@example.com")
    booking = await channel_service.create_channel_booking(committed_conn, **_push(seed))
    await committed_conn.execute(
        "UPDATE outbox_event SET status = 'published' WHERE aggregate_id = $1", booking["id"]
    )
    # The partner subscribes only now, after the event already went out.
    await _subscribe(committed_conn, seed["partner_id"])

    report = await outbox_service.reconciliation(committed_conn)
    assert report["bookings"][0]["delivery_status"] == "no_listener"
