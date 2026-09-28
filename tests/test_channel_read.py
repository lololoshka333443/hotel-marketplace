"""Channel read-API tests: a channel reads tariffs and availability with the
same API key it pushes bookings with.

Invariants this slice guards:
  1. A key only reaches its own partner's inventory — a foreign unit type is a
     404, never a leak of prices or availability.
  2. Prices come back exactly as the partner set them, with the unit's
     base_price where no explicit price row exists.
  3. Closed dates (stop sell, incl. iCal-imported ones) are flagged, so a
     channel does not sell what the partner closed.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import AsyncIterator, Iterator

import asyncpg
import pytest
from starlette.testclient import TestClient

from app.config.settings import settings
from app.modules.auth import service as auth_service
from app.modules.auth.schemas import PartnerRegisterRequest
from app.modules.booking import service as booking_service
from app.modules.channel import service
from app.modules.property import service as property_service
from app.modules.property.schemas import PropertyCreate
from app.modules.rate import service as rate_service

TODAY = dt.date.today()

# Same order as the FK graph; the whole world this module seeds is wiped here.
_CLEANUP = (
    "DELETE FROM outbox_shed_counter; DELETE FROM webhook_delivery; "
    "DELETE FROM outbox_event; "
    "DELETE FROM webhook_subscription; "
    "DELETE FROM api_key; "
    "DELETE FROM ical_subscription; "
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


async def _seed(
    conn: asyncpg.Connection, email: str, *, base_price: float = 3000, total_units: int = 2
) -> dict:
    """Partner + property + unit_type + inventory. Commits on an autocommit conn."""
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
        "VALUES ($1, 'Студия', 2, $2, $3) RETURNING id::text",
        prop.id,
        total_units,
        base_price,
    )
    assert row is not None
    await conn.execute(
        "INSERT INTO inventory_day (unit_type_id, date, available) "
        "SELECT $1, d.date, $2 FROM generate_series("
        "  (CURRENT_DATE - interval '7 days')::date,"
        "  (CURRENT_DATE + interval '89 days')::date, '1 day'"
        ") AS d(date)",
        row["id"],
        total_units,
    )
    return {"unit_type_id": row["id"], "partner_id": partner_id}


def _day(offset: int) -> str:
    return (TODAY + dt.timedelta(days=offset)).isoformat()


# ---------------------------------------------------------------- service: rates


@pytest.mark.asyncio
async def test_rates_reject_other_partners_unit_type(db_conn) -> None:
    """A key resolving to partner B must not read partner A's tariffs."""
    a = await _seed(db_conn, "ra@example.com")
    b = await _seed(db_conn, "rb@example.com")

    with pytest.raises(service.NotOwned):
        await service.get_channel_rates(
            db_conn, b["partner_id"], a["unit_type_id"], TODAY, TODAY + dt.timedelta(days=3)
        )


@pytest.mark.asyncio
async def test_rates_match_what_partner_set(db_conn) -> None:
    """The channel sees exactly the prices the partner cabinet stored."""
    seed = await _seed(db_conn, "rc@example.com", base_price=3000)
    rp = await rate_service.create_rate_plan(db_conn, seed["unit_type_id"], "Сезон")
    await rate_service.set_prices(
        db_conn, rp["id"], TODAY, TODAY + dt.timedelta(days=4), price=5500, min_stay=2
    )

    out = await service.get_channel_rates(
        db_conn,
        seed["partner_id"],
        seed["unit_type_id"],
        TODAY,
        TODAY + dt.timedelta(days=4),
    )
    assert out["unit_type_id"] == seed["unit_type_id"]
    assert out["currency"] == "RUB"
    assert [d["date"] for d in out["days"]] == [_day(i) for i in range(4)]
    assert all(d["price"] == 5500 and d["min_stay"] == 2 for d in out["days"])

    # Cross-check against the partner cabinet's own price read.
    partner_prices = await rate_service.get_prices(
        db_conn, rp["id"], TODAY, TODAY + dt.timedelta(days=4)
    )
    assert [d["price"] for d in out["days"]] == [d["price"] for d in partner_prices]


@pytest.mark.asyncio
async def test_rates_fall_back_to_base_price(db_conn) -> None:
    """No explicit price row -> the unit's base price, with and without a plan."""
    seed = await _seed(db_conn, "rd@example.com", base_price=2500)
    await rate_service.create_rate_plan(db_conn, seed["unit_type_id"], "База")

    out = await service.get_channel_rates(
        db_conn,
        seed["partner_id"],
        seed["unit_type_id"],
        TODAY,
        TODAY + dt.timedelta(days=3),
    )
    assert len(out["days"]) == 3
    assert all(d["price"] == 2500 for d in out["days"])


@pytest.mark.asyncio
async def test_rates_base_price_without_any_plan(db_conn) -> None:
    """A unit type with no rate plan at all still tariffs at base price."""
    seed = await _seed(db_conn, "rd2@example.com", base_price=1990)

    out = await service.get_channel_rates(
        db_conn,
        seed["partner_id"],
        seed["unit_type_id"],
        TODAY,
        TODAY + dt.timedelta(days=2),
    )
    assert all(d["price"] == 1990 for d in out["days"])


@pytest.mark.asyncio
async def test_rates_reject_bad_range(db_conn) -> None:
    seed = await _seed(db_conn, "re@example.com")

    with pytest.raises(service.BadRange):
        await service.get_channel_rates(
            db_conn, seed["partner_id"], seed["unit_type_id"], TODAY, TODAY
        )
    with pytest.raises(service.BadRange):
        await service.get_channel_rates(
            db_conn,
            seed["partner_id"],
            seed["unit_type_id"],
            TODAY,
            TODAY + dt.timedelta(days=200),
        )


# ------------------------------------------------------- service: availability


@pytest.mark.asyncio
async def test_availability_reject_other_partners_unit_type(db_conn) -> None:
    a = await _seed(db_conn, "rfa@example.com")
    b = await _seed(db_conn, "rfb@example.com")

    with pytest.raises(service.NotOwned):
        await service.get_channel_availability(
            db_conn, b["partner_id"], a["unit_type_id"], TODAY, TODAY + dt.timedelta(days=3)
        )


@pytest.mark.asyncio
async def test_availability_counts_hold_and_closed(db_conn) -> None:
    """free = available - hold - sold; a closed date is flagged, not bookable."""
    seed = await _seed(db_conn, "rg@example.com", total_units=2)
    ut = seed["unit_type_id"]

    # A manual stop sell on one date.
    await db_conn.execute(
        "UPDATE inventory_day SET closed = true WHERE unit_type_id = $1 AND date = $2",
        ut,
        TODAY + dt.timedelta(days=5),
    )
    # A price_day stop sell on another (the channel must honour tariffs too).
    rp = await rate_service.create_rate_plan(db_conn, ut, "Сезон")
    await db_conn.execute(
        "INSERT INTO price_day (rate_plan_id, date, price, stop_sell) VALUES ($1, $2, 100, true)",
        rp["id"],
        TODAY + dt.timedelta(days=6),
    )
    # One unit of two held for two nights. The outer fixture transaction is
    # already open; create_hold only needs to be inside *a* transaction.
    await booking_service.create_hold(
        db_conn,
        unit_type_id=ut,
        checkin=TODAY + dt.timedelta(days=10),
        checkout=TODAY + dt.timedelta(days=12),
        guest_name="Иван Гость",
        guest_email=f"g{uuid.uuid4().hex[:6]}@example.com",
        guest_phone="+79991234567",
        idempotency_key=f"k-{uuid.uuid4()}",
    )

    out = await service.get_channel_availability(
        db_conn, seed["partner_id"], ut, TODAY, TODAY + dt.timedelta(days=12)
    )
    assert out["total_units"] == 2
    days = {d["date"]: d for d in out["days"]}

    assert days[_day(1)]["free"] == 2
    assert days[_day(1)]["closed"] is False
    assert days[_day(1)]["bookable"] == 2

    assert days[_day(5)]["closed"] is True
    assert days[_day(5)]["bookable"] == 0
    assert days[_day(6)]["closed"] is True
    assert days[_day(6)]["bookable"] == 0

    assert days[_day(10)]["hold"] == 1
    assert days[_day(10)]["free"] == 1
    assert days[_day(11)]["hold"] == 1 and days[_day(11)]["free"] == 1


@pytest.mark.asyncio
async def test_availability_unreachable_day_is_not_free(db_conn) -> None:
    """A day the inventory generator has not reached yet is reported as full."""
    seed = await _seed(db_conn, "rh@example.com")

    out = await service.get_channel_availability(
        db_conn,
        seed["partner_id"],
        seed["unit_type_id"],
        TODAY + dt.timedelta(days=400),
        TODAY + dt.timedelta(days=402),
    )
    assert [d["free"] for d in out["days"]] == [0, 0]
    assert all(d["closed"] is False for d in out["days"])


# --------------------------------------------------------------------- HTTP face
#
# The app is booted once for the module: the routes own their connections, so
# the seeded world has to be committed and cleaned up afterwards.


@pytest.fixture(scope="module")
async def world() -> AsyncIterator[dict]:
    pool = await asyncpg.create_pool(dsn=settings.database_url, min_size=1, max_size=2)
    conn = await pool.acquire()
    try:
        mine = await _seed(conn, "read-mine@example.com", base_price=3000, total_units=2)
        foreign = await _seed(conn, "read-foreign@example.com", base_price=9000, total_units=1)

        rp = await rate_service.create_rate_plan(conn, mine["unit_type_id"], "Сезон")
        await rate_service.set_prices(
            conn, rp["id"], TODAY, TODAY + dt.timedelta(days=4), price=5500, min_stay=2
        )
        await rate_service.set_prices(
            conn, rp["id"], TODAY + dt.timedelta(days=4), TODAY + dt.timedelta(days=8), price=4200
        )
        await conn.execute(
            "UPDATE inventory_day SET closed = true WHERE unit_type_id = $1 AND date = $2",
            mine["unit_type_id"],
            TODAY + dt.timedelta(days=6),
        )
        key = await service.create_key(conn, mine["partner_id"], "Channel read")
        foreign_key = await service.create_key(conn, foreign["partner_id"], "Other channel")

        yield {
            **mine,
            "rate_plan_id": rp["id"],
            "key": key["key"],
            "foreign_unit_type_id": foreign["unit_type_id"],
            "foreign_key": foreign_key["key"],
        }
    finally:
        await conn.execute(_CLEANUP)
        await pool.release(conn)
        await pool.close()


@pytest.fixture(scope="module")
def client(world: dict) -> Iterator[TestClient]:
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


def test_http_rates_own_unit_type_is_200(client: TestClient, world: dict) -> None:
    resp = client.get(
        "/v1/channel/rates",
        params={"unit_type_id": world["unit_type_id"], "date_from": _day(0), "date_to": _day(8)},
        headers={"X-API-Key": world["key"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["unit_type_id"] == world["unit_type_id"]
    assert body["currency"] == "RUB"
    assert [d["date"] for d in body["days"]] == [_day(i) for i in range(8)]
    prices = [d["price"] for d in body["days"]]
    assert prices[:4] == [5500] * 4
    assert prices[4:8] == [4200] * 4
    assert body["days"][0]["min_stay"] == 2


def test_http_rates_foreign_unit_type_is_404(client: TestClient, world: dict) -> None:
    resp = client.get(
        "/v1/channel/rates",
        params={
            "unit_type_id": world["foreign_unit_type_id"],
            "date_from": _day(0),
            "date_to": _day(3),
        },
        headers={"X-API-Key": world["key"]},
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.parametrize(
    ("headers", "note"),
    [
        ({}, "no key at all"),
        ({"X-API-Key": "hm_live_definitely_not_a_real_key"}, "unknown key"),
    ],
)
def test_http_rates_without_a_key_is_401(
    client: TestClient, world: dict, headers: dict, note: str
) -> None:
    resp = client.get(
        "/v1/channel/rates",
        params={"unit_type_id": world["unit_type_id"], "date_from": _day(0), "date_to": _day(3)},
        headers=headers,
    )
    assert resp.status_code == 401, note


def test_http_rates_bad_range_is_422(client: TestClient, world: dict) -> None:
    resp = client.get(
        "/v1/channel/rates",
        params={"unit_type_id": world["unit_type_id"], "date_from": _day(3), "date_to": _day(0)},
        headers={"X-API-Key": world["key"]},
    )
    assert resp.status_code == 422, resp.text


def test_http_availability_own_unit_type_is_200(client: TestClient, world: dict) -> None:
    resp = client.get(
        "/v1/channel/availability",
        params={"unit_type_id": world["unit_type_id"], "date_from": _day(0), "date_to": _day(8)},
        headers={"X-API-Key": world["key"]},
    )
    assert resp.status_code == 200, resp.text
    days = {d["date"]: d for d in resp.json()["days"]}
    assert resp.json()["total_units"] == 2
    assert days[_day(1)]["free"] == 2
    assert days[_day(1)]["closed"] is False
    # The partner closed this date manually: flagged and not bookable.
    assert days[_day(6)]["closed"] is True
    assert days[_day(6)]["bookable"] == 0


def test_http_availability_foreign_unit_type_is_404(client: TestClient, world: dict) -> None:
    resp = client.get(
        "/v1/channel/availability",
        params={
            "unit_type_id": world["foreign_unit_type_id"],
            "date_from": _day(0),
            "date_to": _day(3),
        },
        headers={"X-API-Key": world["key"]},
    )
    assert resp.status_code == 404, resp.text
