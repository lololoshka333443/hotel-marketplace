"""Outbox tests: emit → deliver → reconcile.

The contract this slice guards:
  1. An event is written inside the same transaction as its change — if the
     business commit rolls back, no event exists either.
  2. Delivery is signed, idempotent per (event, subscription), and a flaky
     subscriber does not block a healthy one.
  3. Repeated failure dead-letters instead of looping forever.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import uuid

import asyncpg
import pytest

from app.modules.auth import service as auth_service
from app.modules.auth.schemas import PartnerRegisterRequest
from app.modules.outbox import deliver, service, worker
from app.modules.property import service as property_service
from app.modules.property.schemas import PropertyCreate
from tests._subs import subscribe

TODAY = dt.date.today()


async def _seed(conn: asyncpg.Connection, email: str) -> dict:
    partner_id = await auth_service.register_partner(
        conn, PartnerRegisterRequest(email=email, password="secret123", name="Tester")
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
        "VALUES ($1, 'Квартира', 2, 1, 3000) RETURNING id::text",
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
    return {
        "unit_type_id": row["id"],
        "property_id": str(prop.id),
        "partner_id": str(partner_id),
    }


async def _subscribe(
    conn, partner_id: str, url: str, secret="very-very-secret", event_types=("*",)
) -> dict:
    """Insert a subscription the way the API route does: secret sealed at rest."""
    sub_id = await subscribe(conn, partner_id, url, secret, tuple(event_types))
    return {"id": sub_id, "url": url, "secret": secret}


def _event_row(row: asyncpg.Record) -> dict:
    return dict(row)


# ---------------------------------------------------------------- emit


@pytest.mark.asyncio
async def test_emit_writes_row(committed_conn) -> None:
    seed = await _seed(committed_conn, "w1@example.com")
    await service.emit(
        committed_conn,
        aggregate="property",
        aggregate_id=seed["property_id"],
        event_type=service.PROPERTY_STATUS_CHANGED,
        payload={"status": "published"},
        property_id=seed["property_id"],
    )
    row = await committed_conn.fetchrow("SELECT * FROM outbox_event")
    assert row is not None
    assert row["status"] == "pending"
    assert row["attempts"] == 0
    assert json.loads(row["payload"]) == {"status": "published"}
    assert str(row["property_id"]) == seed["property_id"]


@pytest.mark.asyncio
async def test_emit_failure_does_not_break_the_caller(db_conn, monkeypatch) -> None:
    """A broken outbox must never roll back the business change."""
    import asyncpg

    async def boom(*a, **k):
        raise RuntimeError("db gone")

    # The proxy exposes execute read-only, so patch the connection class.
    monkeypatch.setattr(asyncpg.Connection, "execute", boom)
    # Must not raise.
    await service.emit(
        db_conn,
        aggregate="property",
        aggregate_id="p1",
        event_type=service.PROPERTY_STATUS_CHANGED,
        payload={},
        property_id=None,
    )


@pytest.mark.asyncio
async def test_emit_rolls_back_with_the_transaction(committed_conn) -> None:
    """The event shares the transaction of the change it describes."""
    seed = await _seed(committed_conn, "e1@example.com")

    try:
        async with committed_conn.transaction():
            await committed_conn.execute(
                "UPDATE property SET status = 'blocked' WHERE id = $1",
                seed["property_id"],
            )
            await service.emit(
                committed_conn,
                aggregate="property",
                aggregate_id=seed["property_id"],
                event_type=service.PROPERTY_STATUS_CHANGED,
                payload={"status": "blocked"},
                property_id=seed["property_id"],
            )
            raise RuntimeError("simulate caller failure")
    except RuntimeError:
        pass

    assert await committed_conn.fetchval("SELECT count(*) FROM outbox_event") == 0
    status = await committed_conn.fetchval(
        "SELECT status FROM property WHERE id = $1", seed["property_id"]
    )
    assert status == "draft"


# ---------------------------------------------------------------- claim / deliver


@pytest.mark.asyncio
async def test_claim_marks_delivering_and_orders_by_happened(committed_conn) -> None:
    for i in range(3):
        await service.emit(
            committed_conn,
            aggregate="property",
            aggregate_id=f"p{i}",
            event_type=service.PROPERTY_STATUS_CHANGED,
            payload={"i": i},
            property_id=None,
        )
        await committed_conn.execute("SELECT pg_sleep(0.01)")

    claimed = await service.claim_due(committed_conn, 2)
    assert len(claimed) == 2
    first_payload = (
        json.loads(claimed[0]["payload"])
        if isinstance(claimed[0]["payload"], str)
        else claimed[0]["payload"]
    )
    assert first_payload["i"] == 0  # oldest first
    statuses = [r["status"] for r in await committed_conn.fetch("SELECT status FROM outbox_event")]
    assert statuses.count("delivering") == 2
    assert statuses.count("pending") == 1


@pytest.mark.asyncio
async def test_reclaim_stale_returns_orphans(committed_conn) -> None:
    await service.emit(
        committed_conn,
        aggregate="property",
        aggregate_id="p1",
        event_type=service.PROPERTY_STATUS_CHANGED,
        payload={},
        property_id=None,
    )
    await service.claim_due(committed_conn, 10)
    # Simulate a worker that died mid-flight.
    await committed_conn.execute(
        "UPDATE outbox_event SET claimed_at = now() - interval '1 hour' WHERE status='delivering'"
    )
    n = await service.reclaim_stale(committed_conn, 300)
    assert n == 1
    assert await committed_conn.fetchval("SELECT status FROM outbox_event") == "pending"


@pytest.mark.asyncio
async def test_sign_is_hmac_sha256() -> None:
    body = b'{"a":1}'
    sig = deliver.sign(body, "s3cret")
    expected = hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    assert sig == expected
    assert len(sig) == 64


@pytest.mark.asyncio
async def test_deliver_success(db_conn, monkeypatch) -> None:
    seed = await _seed(db_conn, "d1@example.com")
    sub = await _subscribe(db_conn, seed["partner_id"], "https://ch.example/hook")
    await service.emit(
        db_conn,
        aggregate="property",
        aggregate_id=seed["property_id"],
        event_type=service.PROPERTY_STATUS_CHANGED,
        payload={"status": "blocked"},
        property_id=seed["property_id"],
    )
    [event] = await service.claim_due(db_conn, 10)

    captured = {}

    async def fake_deliver(url, secret, ev):
        assert url == sub["url"]
        assert secret == sub["secret"]
        assert ev["event_type"] == service.PROPERTY_STATUS_CHANGED
        captured["body"] = json.dumps(ev, default=str).encode()
        return True, 200, None

    monkeypatch.setattr(deliver, "deliver", fake_deliver)

    await worker._deliver_one(db_conn, event)

    # Signed body, event delivered, event closed.
    assert hmac.compare_digest(
        deliver.sign(captured["body"], sub["secret"]),
        deliver.sign(captured["body"], "very-very-secret"),
    )
    assert await db_conn.fetchval("SELECT status FROM outbox_event") == "published"
    row = await db_conn.fetchrow(
        "SELECT status, status_code FROM webhook_delivery WHERE event_id = $1",
        event["id"],
    )
    assert row["status"] == "success"
    assert row["status_code"] == 200


@pytest.mark.asyncio
async def test_deliver_failure_backoff_then_dead_letter(committed_conn, monkeypatch) -> None:
    """A failing subscriber is retried with backoff, then dead-lettered."""
    seed = await _seed(committed_conn, "d2@example.com")
    await _subscribe(committed_conn, seed["partner_id"], "https://ch.example/hook")
    await service.emit(
        committed_conn,
        aggregate="property",
        aggregate_id=seed["property_id"],
        event_type=service.PROPERTY_STATUS_CHANGED,
        payload={},
        property_id=seed["property_id"],
    )

    async def failing(url, secret, ev):
        return False, 503, "HTTP 503 busy"

    monkeypatch.setattr(deliver, "deliver", failing)

    for attempt in range(1, 7):
        # Backoff pushes next_attempt_at into the future; make it due now.
        await committed_conn.execute(
            "UPDATE outbox_event SET next_attempt_at = now() WHERE status = 'pending'"
        )
        [event] = await service.claim_due(committed_conn, 10)
        await worker._deliver_one(committed_conn, event)
        status = await committed_conn.fetchval("SELECT status FROM outbox_event")
        if attempt < 6:
            assert status == "pending"
            next_at = await committed_conn.fetchval("SELECT next_attempt_at FROM outbox_event")
            assert next_at > dt.datetime.now(dt.UTC)
        else:
            assert status == "failed"

    assert await committed_conn.fetchval("SELECT attempts FROM outbox_event") == 6
    assert await committed_conn.fetchval("SELECT count(*) FROM webhook_delivery") >= 1


@pytest.mark.asyncio
async def test_one_flaky_subscriber_does_not_block_another(committed_conn, monkeypatch) -> None:
    """Partial success: the good hook is not retried, only the bad one is."""
    seed = await _seed(committed_conn, "d3@example.com")
    await _subscribe(committed_conn, seed["partner_id"], "https://good.example/hook")
    bad = await _subscribe(committed_conn, seed["partner_id"], "https://bad.example/hook")

    await service.emit(
        committed_conn,
        aggregate="property",
        aggregate_id=seed["property_id"],
        event_type=service.PROPERTY_STATUS_CHANGED,
        payload={},
        property_id=seed["property_id"],
    )
    [event] = await service.claim_due(committed_conn, 10)

    calls = []

    async def mixed(url, secret, ev):
        calls.append(url)
        if url == bad["url"]:
            return False, 500, "HTTP 500"
        return True, 200, None

    monkeypatch.setattr(deliver, "deliver", mixed)
    await worker._deliver_one(committed_conn, event)
    assert await committed_conn.fetchval("SELECT status FROM outbox_event") == "pending"

    # Second attempt: only the bad hook is contacted again.
    await committed_conn.execute(
        "UPDATE outbox_event SET next_attempt_at = now() WHERE status = 'pending'"
    )
    [event] = await service.claim_due(committed_conn, 10)
    calls.clear()
    await worker._deliver_one(committed_conn, event)
    assert calls == [bad["url"]]

    # The good delivery is not re-sent and stays successful.
    n_ok = await committed_conn.fetchval(
        "SELECT count(*) FROM webhook_delivery WHERE status = 'success'"
    )
    assert n_ok == 1


@pytest.mark.asyncio
async def test_no_subscribers_marks_published(db_conn) -> None:
    seed = await _seed(db_conn, "d4@example.com")
    await service.emit(
        db_conn,
        aggregate="property",
        aggregate_id=seed["property_id"],
        event_type=service.PROPERTY_STATUS_CHANGED,
        payload={},
        property_id=seed["property_id"],
    )
    [event] = await service.claim_due(db_conn, 10)
    await worker._deliver_one(db_conn, event)
    assert await db_conn.fetchval("SELECT status FROM outbox_event") == "published"


@pytest.mark.asyncio
async def test_event_type_filter(db_conn, monkeypatch) -> None:
    """A subscription scoped to one event type does not receive the others."""
    seed = await _seed(db_conn, "d5@example.com")
    await _subscribe(
        db_conn,
        seed["partner_id"],
        "https://ch.example/hook",
        event_types=(service.RATE_PRICES_CHANGED,),
    )

    await service.emit(
        db_conn,
        aggregate="property",
        aggregate_id=seed["property_id"],
        event_type=service.PROPERTY_STATUS_CHANGED,
        payload={},
        property_id=seed["property_id"],
    )
    [event] = await service.claim_due(db_conn, 10)
    subs = await service.subscribers_for(db_conn, event["id"], event["event_type"])
    assert subs == []
    await worker._deliver_one(db_conn, event)
    assert await db_conn.fetchval("SELECT status FROM outbox_event") == "published"


# ---------------------------------------------------------------- real emit points


@pytest.mark.asyncio
async def test_property_status_change_emits(committed_conn) -> None:
    from app.modules.admin import service as admin_service

    seed = await _seed(committed_conn, "a1@example.com")
    row = await admin_service.set_property_status(committed_conn, seed["property_id"], "blocked")
    assert row["status"] == "blocked"

    events = await committed_conn.fetch("SELECT event_type, payload FROM outbox_event")
    assert len(events) == 1
    assert events[0]["event_type"] == service.PROPERTY_STATUS_CHANGED
    assert json.loads(events[0]["payload"])["status"] == "blocked"


@pytest.mark.asyncio
async def test_price_change_emits(committed_conn) -> None:
    from app.modules.rate import service as rate_service

    seed = await _seed(committed_conn, "a2@example.com")
    rp = await rate_service.create_rate_plan(committed_conn, seed["unit_type_id"], "Лето")
    await rate_service.set_prices(
        committed_conn,
        rp["id"],
        TODAY + dt.timedelta(days=10),
        TODAY + dt.timedelta(days=12),
        4500.0,
    )

    row = await committed_conn.fetchrow("SELECT * FROM outbox_event")
    assert row is not None
    assert row["event_type"] == service.RATE_PRICES_CHANGED
    assert json.loads(row["payload"])["price"] == 4500.0
    assert row["property_id"] == uuid.UUID(seed["property_id"])


@pytest.mark.asyncio
async def test_inventory_close_emits(committed_conn) -> None:
    from app.modules.inventory import service as inventory_service

    seed = await _seed(committed_conn, "a3@example.com")
    n = await inventory_service.close_range(
        committed_conn,
        seed["unit_type_id"],
        TODAY + dt.timedelta(days=10),
        TODAY + dt.timedelta(days=12),
        closed=True,
    )
    assert n == 2

    row = await committed_conn.fetchrow("SELECT * FROM outbox_event")
    assert row is not None
    assert row["event_type"] == service.INVENTORY_AVAILABILITY_CHANGED
    assert json.loads(row["payload"])["closed"] is True


@pytest.mark.asyncio
async def test_booking_confirmed_and_cancelled_emit(committed_conn) -> None:
    """The two events a channel cares most about."""
    from app.modules.booking import service as booking_service
    from app.modules.payment import service as payment_service

    seed = await _seed(committed_conn, "a4@example.com")
    booking = await booking_service.create_hold(
        committed_conn,
        unit_type_id=seed["unit_type_id"],
        checkin=TODAY + dt.timedelta(days=10),
        checkout=TODAY + dt.timedelta(days=12),
        idempotency_key=f"k-{uuid.uuid4()}",
        guest_name="Иван Гость",
        guest_email="i@example.com",
        guest_phone="+79991234567",
    )
    await payment_service.pay_and_confirm(booking["id"], conn=committed_conn)

    types = [
        r["event_type"]
        for r in await committed_conn.fetch(
            "SELECT event_type FROM outbox_event ORDER BY happened_at"
        )
    ]
    assert service.BOOKING_CONFIRMED in types

    await payment_service.refund_booking(booking["id"], conn=committed_conn)
    types = [
        r["event_type"]
        for r in await committed_conn.fetch(
            "SELECT event_type FROM outbox_event ORDER BY happened_at"
        )
    ]
    assert service.BOOKING_CANCELLED in types
