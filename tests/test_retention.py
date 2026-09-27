"""Retention for the webhook delivery ledger.

The table grows one row per event per subscription and reconciliation reads it,
so it cannot be dropped wholesale — it ages out on purpose: partitioned by
delivered_at (monthly), successes pruned after a short window, failures after a
much longer one, and empty old partitions dropped. These tests cover the sweep
itself and that reconciliation still answers on a ledger it has thinned.
"""

from __future__ import annotations

import datetime as dt
import uuid

import asyncpg
import pytest

from app.modules.auth import service as auth_service
from app.modules.auth.schemas import PartnerRegisterRequest
from app.modules.channel import service as channel_service
from app.modules.outbox import retention
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
        client_key=f"ret-{uuid.uuid4()}",
    )


async def _subscribe(conn: asyncpg.Connection, partner_id: str) -> str:
    return await conn.fetchval(
        """
        INSERT INTO webhook_subscription (partner_id, url, secret, event_types)
        VALUES ($1, 'http://localhost:9/hooks', 'ret-secret-ret', '{*}')
        RETURNING id::text
        """,
        partner_id,
    )


async def _delivery(
    conn: asyncpg.Connection,
    *,
    event_id: str | None = None,
    subscription_id: str,
    status: str,
    days_ago: int,
) -> str:
    """Write a delivery row aged `days_ago`, routed by its own timestamp.

    Without an event_id the row gets a synthetic one: the ledger no longer
    foreign-keys to outbox_event, and retention only ever keys on status and
    delivered_at.
    """
    delivery_id = str(uuid.uuid4())
    await conn.execute(
        """
        INSERT INTO webhook_delivery (id, event_id, subscription_id, status, delivered_at)
        VALUES ($1, $2, $3, $4, now() - ($5 || ' days')::interval)
        """,
        delivery_id,
        event_id if event_id is not None else str(uuid.uuid4()),
        subscription_id,
        status,
        str(days_ago),
    )
    return delivery_id


async def _partition_names(conn: asyncpg.Connection) -> set[str]:
    rows = await conn.fetch(
        """
        SELECT c.relname AS name
        FROM pg_inherits i
        JOIN pg_class c ON c.oid = i.inhrelid
        JOIN pg_class p ON p.oid = i.inhparent
        WHERE p.relname = 'webhook_delivery'
        """
    )
    return {r["name"] for r in rows}


def _expected_months(count: int) -> list[str]:
    month = TODAY.replace(day=1)
    return [
        f"webhook_delivery_{(month + dt.timedelta(days=32 * i)).replace(day=1):%Y%m}"
        for i in range(count)
    ]


@pytest.mark.asyncio
async def test_partitions_are_created_months_ahead(committed_conn) -> None:
    """The sweep hands out this month plus headroom, so a delivery is never
    blocked on a partition that does not exist yet."""
    created = await retention.ensure_partitions(committed_conn, ahead_months=3)

    assert created == _expected_months(4)
    assert set(created) <= await _partition_names(committed_conn)
    # Calling again is a no-op — the sweep runs on a schedule.
    again = await retention.ensure_partitions(committed_conn, ahead_months=3)
    assert again == created


@pytest.mark.asyncio
async def test_a_delivery_lands_in_its_own_months_partition(committed_conn) -> None:
    await retention.ensure_partitions(committed_conn, ahead_months=3)
    seed = await _seed(committed_conn, "ret1@example.com")
    sub_id = await _subscribe(committed_conn, seed["partner_id"])
    booking = await channel_service.create_channel_booking(committed_conn, **_push(seed))
    event_id = await committed_conn.fetchval(
        "SELECT id::text FROM outbox_event WHERE aggregate_id = $1", booking["id"]
    )
    assert event_id is not None

    await outbox_service.record_delivery(committed_conn, event_id, sub_id, True, 200, None)

    landed = await committed_conn.fetchval(
        "SELECT tableoid::regclass::text FROM webhook_delivery WHERE event_id = $1",
        event_id,
    )
    assert landed == f"webhook_delivery_{TODAY.replace(day=1):%Y%m}"


@pytest.mark.asyncio
async def test_old_successes_are_pruned_and_failures_kept(committed_conn) -> None:
    """A success is only the proof, so it goes first; a failure is what a
    reconciliation question is about, so it outlives it."""
    seed = await _seed(committed_conn, "ret2@example.com")
    sub_id = await _subscribe(committed_conn, seed["partner_id"])
    ok = await _delivery(committed_conn, subscription_id=sub_id, status="success", days_ago=60)
    bad = await _delivery(committed_conn, subscription_id=sub_id, status="failed", days_ago=60)

    pruned = await retention.prune_deliveries(committed_conn, success_days=30, failed_days=365)

    assert pruned == {"success": 1, "failed": 0}
    kept = await committed_conn.fetch("SELECT id FROM webhook_delivery")
    assert len(kept) == 1
    assert kept[0]["id"] == uuid.UUID(bad)
    assert uuid.UUID(ok) not in {r["id"] for r in kept}


@pytest.mark.asyncio
async def test_failures_age_out_after_their_own_window(committed_conn) -> None:
    seed = await _seed(committed_conn, "ret3@example.com")
    sub_id = await _subscribe(committed_conn, seed["partner_id"])
    await _delivery(committed_conn, subscription_id=sub_id, status="failed", days_ago=400)

    pruned = await retention.prune_deliveries(committed_conn, success_days=30, failed_days=365)

    assert pruned == {"success": 0, "failed": 1}
    assert await committed_conn.fetchval("SELECT count(*) FROM webhook_delivery") == 0


@pytest.mark.asyncio
async def test_recent_rows_are_untouched(committed_conn) -> None:
    seed = await _seed(committed_conn, "ret4@example.com")
    sub_id = await _subscribe(committed_conn, seed["partner_id"])
    await _delivery(committed_conn, subscription_id=sub_id, status="success", days_ago=5)

    pruned = await retention.prune_deliveries(committed_conn, success_days=30, failed_days=365)

    assert pruned == {"success": 0, "failed": 0}
    assert await committed_conn.fetchval("SELECT count(*) FROM webhook_delivery") == 1


@pytest.mark.asyncio
async def test_empty_old_partitions_are_dropped_kept_when_holding_failures(
    committed_conn,
) -> None:
    """A partition older than the whole window is dropped, but only once it is
    empty — a failed delivery in it is still a question to answer."""
    old_month = dt.date(2020, 1, 1)
    empty_month = dt.date(2020, 2, 1)
    for month in (old_month, empty_month):
        end = (month + dt.timedelta(days=32)).replace(day=1)
        await committed_conn.execute(f"DROP TABLE IF EXISTS webhook_delivery_{month:%Y%m}")
        await committed_conn.execute(
            f"CREATE TABLE webhook_delivery_{month:%Y%m} "
            f"PARTITION OF webhook_delivery "
            f"FOR VALUES FROM ('{month.isoformat()}') TO ('{end.isoformat()}')"
        )
    seed = await _seed(committed_conn, "ret5@example.com")
    sub_id = await _subscribe(committed_conn, seed["partner_id"])
    await _delivery(
        committed_conn,
        subscription_id=sub_id,
        status="failed",
        days_ago=(TODAY - old_month).days - 10,
    )

    dropped = await retention.drop_empty_old_partitions(committed_conn, failed_days=365)

    assert dropped == [f"webhook_delivery_{empty_month:%Y%m}"]
    names = await _partition_names(committed_conn)
    assert f"webhook_delivery_{old_month:%Y%m}" in names
    assert f"webhook_delivery_{empty_month:%Y%m}" not in names


@pytest.mark.asyncio
async def test_reconciliation_survives_a_pruned_ledger(committed_conn) -> None:
    """The report still answers when retention has thinned the ledger: a fully
    pruned proof degrades to `undelivered`, a half-pruned one to `partial` —
    the same states a live missing delivery produces."""
    seed = await _seed(committed_conn, "ret6@example.com")
    kept_sub = await _subscribe(committed_conn, seed["partner_id"])
    aged_sub = await _subscribe(committed_conn, seed["partner_id"])
    booking = await channel_service.create_channel_booking(committed_conn, **_push(seed))
    event_id = await committed_conn.fetchval(
        "SELECT id::text FROM outbox_event WHERE aggregate_id = $1", booking["id"]
    )
    assert event_id is not None
    await outbox_service.record_delivery(committed_conn, event_id, kept_sub, True, 200, None)
    await outbox_service.record_delivery(committed_conn, event_id, aged_sub, True, 200, None)
    await outbox_service.mark_published(committed_conn, event_id)

    delivered = await outbox_service.reconciliation(committed_conn)
    assert delivered["bookings"][0]["delivery_status"] == "delivered"
    assert delivered["summary"]["delivered"] == 1

    # Retention ages out one of the two proofs — on a fresh partition, not by
    # dropping the table from under the report.
    await committed_conn.execute(
        "UPDATE webhook_delivery SET delivered_at = now() - interval '60 days' "
        "WHERE subscription_id = $1",
        aged_sub,
    )
    pruned = await retention.prune_deliveries(committed_conn, success_days=30, failed_days=365)
    assert pruned == {"success": 1, "failed": 0}

    partial = await outbox_service.reconciliation(committed_conn)
    row = partial["bookings"][0]
    assert row["delivery_status"] == "partial"
    assert row["event"]["expected_subscribers"] == 2
    assert row["event"]["delivered_ok"] == 1
    assert partial["summary"]["partial"] == 1

    # Even a ledger with no proof at all is a report, not an error.
    await retention.prune_deliveries(committed_conn, success_days=0, failed_days=0)
    emptied = await outbox_service.reconciliation(committed_conn)
    assert emptied["bookings"][0]["delivery_status"] == "undelivered"
    assert emptied["summary"]["undelivered"] == 1
