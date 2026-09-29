"""Rate-limit tests: the channel API and webhook delivery.

Invariants this slice guards:
  1. Over the limit -> 429 with a Retry-After, not a silent success and not a
     500. Under the limit, nothing changes.
  2. Read and write buckets are separate: a channel reading tariffs does not
     spend its booking budget.
  3. A window that passes is a budget that comes back.
  4. A throttled webhook subscription is retried, never dead-lettered: a rate
     limit is not an error, and it costs no attempt.
  5. A broken/absent Redis fails open rather than taking the API down.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import time
import uuid
from collections.abc import AsyncIterator, Iterator

import asyncpg
import pytest
from starlette.testclient import TestClient

from app.config.settings import settings
from app.modules.auth import service as auth_service
from app.modules.auth.schemas import PartnerRegisterRequest
from app.modules.channel import service as channel_service
from app.modules.outbox import service as outbox_service
from app.modules.outbox import worker
from app.modules.property import service as property_service
from app.modules.property.schemas import PropertyCreate
from app.utils import ratelimit
from tests._subs import subscribe

TODAY = dt.date.today()

_CLEANUP = (
    "DELETE FROM outbox_shed_counter; DELETE FROM webhook_delivery; "
    "DELETE FROM outbox_event; "
    "DELETE FROM webhook_subscription; "
    "DELETE FROM api_key; "
    "DELETE FROM booking_line; "
    "DELETE FROM payment; "
    "DELETE FROM booking; "
    "DELETE FROM inventory_day; "
    "DELETE FROM price_day; "
    "DELETE FROM rate_plan; "
    "DELETE FROM unit_type; "
    "DELETE FROM property; "
    "DELETE FROM partner; "
    "DELETE FROM admin;"
)

# Tight limits for the whole module: 2 reads / 1 write per 1-second window.
_TEST_READ_LIMIT = 2
_TEST_WRITE_LIMIT = 1
_TEST_WINDOW_SEC = 1


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
        "VALUES ($1, 'Студия', 2, 2, 3000) RETURNING id::text",
        prop.id,
    )
    assert row is not None
    await conn.execute(
        "INSERT INTO inventory_day (unit_type_id, date, available) "
        "SELECT $1, d.date, 2 FROM generate_series("
        "  (CURRENT_DATE - interval '7 days')::date,"
        "  (CURRENT_DATE + interval '89 days')::date, '1 day'"
        ") AS d(date)",
        row["id"],
    )
    return {"unit_type_id": row["id"], "partner_id": partner_id}


def _day(offset: int) -> str:
    return (TODAY + dt.timedelta(days=offset)).isoformat()


@pytest.fixture
async def fresh_redis() -> AsyncIterator:
    """A Redis client for *this* test's event loop, installed as the singleton.

    The app inits its own client inside the TestClient's portal loop; the
    asyncpg/redis clients are loop-bound, so a test that touches Redis
    directly must install one that lives in its own loop.
    """
    from app.utils import redis as redis_module

    old = redis_module._client
    client = redis_module.redis.from_url(settings.redis_url, decode_responses=True)
    redis_module._client = client
    try:
        yield client
    finally:
        with contextlib.suppress(Exception):
            async for key in client.scan_iter(match="rl:*"):
                await client.delete(key)
        await client.aclose()
        redis_module._client = old


# ------------------------------------------------------------------ the limiter


@pytest.mark.asyncio
async def test_acquire_counts_a_window(fresh_redis) -> None:
    allowed, retry_after = await ratelimit.acquire("rl:test:w", 2, 60)
    assert allowed is True and retry_after == 0
    allowed, _ = await ratelimit.acquire("rl:test:w", 2, 60)
    assert allowed is True
    allowed, retry_after = await ratelimit.acquire("rl:test:w", 2, 60)
    assert allowed is False
    # The advice is bounded by the window, never nonsense.
    assert 1 <= retry_after <= 60


@pytest.mark.asyncio
async def test_acquire_window_expires(fresh_redis) -> None:
    """A window that passes is a budget that comes back."""
    assert await ratelimit.acquire("rl:test:e", 1, 1) == (True, 0)
    assert (await ratelimit.acquire("rl:test:e", 1, 1))[0] is False

    await asyncio.sleep(1.2)
    assert await ratelimit.acquire("rl:test:e", 1, 1) == (True, 0)


@pytest.mark.asyncio
async def test_acquire_zero_limit_blocks(fresh_redis) -> None:
    """A zero limit is an off switch (used to simulate saturation in tests)."""
    assert await ratelimit.acquire("rl:test:z", 0, 5) == (False, 5)


@pytest.mark.asyncio
async def test_acquire_fails_open_without_redis(monkeypatch) -> None:
    """No Redis -> the call is allowed. The limiter must not take the API down."""

    def _boom():
        raise RuntimeError("Redis is not initialised")

    monkeypatch.setattr("app.utils.ratelimit.get_redis", _boom)
    assert await ratelimit.acquire("rl:test:noredis", 1, 60) == (True, 0)


# --------------------------------------------------------------- channel routes
#
# The app is booted once for the module (its lifespan inits Redis); limits are
# patched low so assertions do not have to sleep through a real minute.


@pytest.fixture(scope="module")
async def world() -> AsyncIterator[dict]:
    pool = await asyncpg.create_pool(dsn=settings.database_url, min_size=1, max_size=2)
    conn = await pool.acquire()
    try:
        mine = await _seed(conn, "rl-mine@example.com")
        key = await channel_service.create_key(conn, mine["partner_id"], "Channel")
        yield {**mine, "key": key["key"]}
    finally:
        await conn.execute(_CLEANUP)
        await pool.release(conn)
        await pool.close()


@pytest.fixture(scope="module")
def client(world: dict) -> Iterator[TestClient]:
    from app.main import create_app

    saved = (
        settings.channel_read_limit_per_min,
        settings.channel_write_limit_per_min,
        settings.rate_limit_window_sec,
    )
    settings.channel_read_limit_per_min = _TEST_READ_LIMIT
    settings.channel_write_limit_per_min = _TEST_WRITE_LIMIT
    settings.rate_limit_window_sec = _TEST_WINDOW_SEC
    try:
        with TestClient(create_app()) as test_client:
            yield test_client
    finally:
        (
            settings.channel_read_limit_per_min,
            settings.channel_write_limit_per_min,
            settings.rate_limit_window_sec,
        ) = saved


def _rates(client: TestClient, world: dict) -> int:
    return client.get(
        "/v1/channel/rates",
        params={"unit_type_id": world["unit_type_id"], "date_from": _day(0), "date_to": _day(3)},
        headers={"X-API-Key": world["key"]},
    ).status_code


def _fresh_window() -> None:
    """Wait until any 1-second window definitely rolled over."""
    time.sleep(_TEST_WINDOW_SEC + 0.3)


def test_read_budget_is_spent_then_refilled(client: TestClient, world: dict) -> None:
    _fresh_window()
    assert _rates(client, world) == 200
    assert _rates(client, world) == 200
    over = client.get(
        "/v1/channel/rates",
        params={"unit_type_id": world["unit_type_id"], "date_from": _day(0), "date_to": _day(3)},
        headers={"X-API-Key": world["key"]},
    )
    assert over.status_code == 429, over.text
    assert int(over.headers["Retry-After"]) >= 1

    # The window passes -> the budget is back.
    _fresh_window()
    assert _rates(client, world) == 200


def test_read_and_write_buckets_are_separate(client: TestClient, world: dict) -> None:
    """Reading tariffs does not eat the booking budget."""
    _fresh_window()
    for _ in range(_TEST_READ_LIMIT):
        assert _rates(client, world) == 200
    # Read budget is gone...
    assert _rates(client, world) == 429
    # ...but a booking still goes through.
    resp = client.post(
        "/v1/channel/bookings",
        json={
            "unit_type_id": world["unit_type_id"],
            "checkin": _day(20),
            "checkout": _day(22),
            "guest": {"name": "Иван", "email": "g-rl@example.com", "phone": "+79991234567"},
            "idempotency_key": f"rl-{uuid.uuid4()}",
        },
        headers={"X-API-Key": world["key"]},
    )
    assert resp.status_code == 201, resp.text


def test_write_limit_returns_429(client: TestClient, world: dict) -> None:
    _fresh_window()
    payload = {
        "unit_type_id": world["unit_type_id"],
        "checkin": _day(30),
        "checkout": _day(31),
        "guest": {"name": "Иван", "email": "g-rl2@example.com", "phone": "+79991234567"},
        "idempotency_key": f"rl-{uuid.uuid4()}",
    }
    first = client.post("/v1/channel/bookings", json=payload, headers={"X-API-Key": world["key"]})
    assert first.status_code == 201, first.text
    second = client.post(
        "/v1/channel/bookings",
        json={**payload, "idempotency_key": f"rl-{uuid.uuid4()}"},
        headers={"X-API-Key": world["key"]},
    )
    assert second.status_code == 429, second.text


def test_401_still_trumps_429(client: TestClient, world: dict) -> None:
    """An unauthenticated call never spends anybody's budget."""
    _fresh_window()
    for _ in range(3):
        resp = client.get(
            "/v1/channel/rates",
            params={
                "unit_type_id": world["unit_type_id"],
                "date_from": _day(0),
                "date_to": _day(3),
            },
            headers={"X-API-Key": "hm_live_bogus"},
        )
        assert resp.status_code == 401
    # The real key's budget is untouched.
    assert _rates(client, world) == 200


# ------------------------------------------------- delivery throttling (worker)


@pytest.mark.asyncio
async def test_throttled_delivery_does_not_burn_an_attempt(db_conn, fresh_redis) -> None:
    """A rate-limited subscriber gets the event later, with no attempt spent."""
    # The module-scoped app is alive and its bookings left events behind; this
    # transaction rolls back, so claiming only ours below is all we need.
    await db_conn.execute("DELETE FROM outbox_event")
    seed = await _seed(db_conn, "rl-deliv@example.com")
    sub_id = await subscribe(
        db_conn, seed["partner_id"], "http://localhost:9/hooks", "s3cr3t-s3cr3t"
    )
    await outbox_service.emit(
        db_conn,
        aggregate="booking",
        aggregate_id=str(uuid.uuid4()),
        event_type=outbox_service.BOOKING_CONFIRMED,
        payload={"hello": "world"},
        property_id=await db_conn.fetchval(
            "SELECT property_id::text FROM unit_type WHERE id = $1", seed["unit_type_id"]
        ),
    )
    events = await outbox_service.claim_due(db_conn)
    assert len(events) == 1

    # Saturate the subscriber's delivery window so the worker must throttle.
    await fresh_redis.set(f"rl:deliver:{sub_id}", 999, ex=60)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(settings, "webhook_rate_per_sec", 1)
    try:
        await worker._deliver_one(db_conn, events[0])
    finally:
        monkeypatch.undo()

    row = await db_conn.fetchrow(
        "SELECT status, attempts FROM outbox_event WHERE id = $1", events[0]["id"]
    )
    # Back in the queue, no attempt spent: a rate limit is not a failure.
    assert row["status"] == "pending"
    assert row["attempts"] == 0
    delivered = await db_conn.fetchval(
        "SELECT count(*) FROM webhook_delivery WHERE subscription_id = $1", sub_id
    )
    assert delivered == 0


@pytest.mark.asyncio
async def test_queue_metrics_shape(committed_conn) -> None:
    await committed_conn.execute(_CLEANUP)
    seed = await _seed(committed_conn, "rl-metrics@example.com")
    pid = await committed_conn.fetchval(
        "SELECT property_id::text FROM unit_type WHERE id = $1", seed["unit_type_id"]
    )
    for event_type in (outbox_service.BOOKING_CONFIRMED, outbox_service.BOOKING_CANCELLED):
        await outbox_service.emit(
            committed_conn,
            aggregate="booking",
            aggregate_id=str(uuid.uuid4()),
            event_type=event_type,
            payload={},
            property_id=pid,
        )

    metrics = await outbox_service.queue_metrics(committed_conn)
    assert metrics["pending"] == 2
    assert metrics["delivering"] == 0
    assert metrics["failed"] == 0
    assert set(metrics) == {
        "pending",
        "delivering",
        "failed",
        "scheduled_for_retry",
        "median_latency_sec",
        "oldest_pending_sec",
        "depth_limit",
        "lag_alert_sec",
        "shed_total",
        "shard_count",
        "workers",
    }
    # The strip shows the configured lines, not guessed ones.
    assert metrics["depth_limit"] == settings.outbox_max_pending
    assert metrics["lag_alert_sec"] == settings.outbox_lag_alert_sec
    assert metrics["shed_total"] == 0
    assert metrics["shard_count"] == settings.outbox_shard_count
    assert metrics["workers"] == settings.outbox_workers
