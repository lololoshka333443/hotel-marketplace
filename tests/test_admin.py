"""Slice 6 tests: cancellation rule + commission reports."""

from __future__ import annotations

import datetime as dt
import uuid

import asyncpg
import pytest

from app.modules.admin import report
from app.modules.auth import service as auth_service
from app.modules.auth.schemas import PartnerRegisterRequest
from app.modules.booking import service as booking_service
from app.modules.payment import service as payment_service
from app.modules.property import service as property_service
from app.modules.property.schemas import PropertyCreate

TODAY = dt.date.today()


async def _seed(conn: asyncpg.Connection, email: str, base_price: float = 3000) -> dict:
    partner_id = await auth_service.register_partner(
        conn, PartnerRegisterRequest(email=email, password="secret123", name="Tester")
    )
    prop = await property_service.create_property(
        conn,
        partner_id,
        PropertyCreate(
            name="Test", property_type="apartment", city="Yalta", timezone="Europe/Simferopol"
        ),
    )
    row = await conn.fetchrow(
        "INSERT INTO unit_type (property_id, name, capacity, total_units, base_price) "
        "VALUES ($1, 'Квартира', 2, 1, $2) RETURNING id::text",
        prop.id,
        base_price,
    )
    assert row is not None
    await conn.execute(
        "INSERT INTO inventory_day (unit_type_id, date, available) "
        "SELECT $1, d.date, 1 FROM generate_series($2::date, ($2::date + 59)::date, '1 day') AS d(date)",
        row["id"],
        TODAY,
    )
    return {"unit_type_id": row["id"], "partner_id": str(partner_id)}


def _guest() -> dict:
    return {
        "guest_name": "Иван Гость",
        "guest_email": f"g{uuid.uuid4().hex[:6]}@example.com",
        "guest_phone": "+79991234567",
    }


async def _confirmed(conn: asyncpg.Connection, ut: str, checkin: dt.date, nights: int = 2) -> str:
    b = await booking_service.create_hold(
        conn,
        unit_type_id=ut,
        checkin=checkin,
        checkout=checkin + dt.timedelta(days=nights),
        idempotency_key=f"k-{uuid.uuid4()}",
        **_guest(),
    )
    await payment_service.pay_and_confirm(b["id"], conn=conn)
    return b["id"]


# ---------------------------------------------------------------- cancellation rule


@pytest.mark.asyncio
async def test_free_cancellation_before_deadline(committed_conn) -> None:
    """Cancelling well before check-in is free."""
    seed = await _seed(committed_conn, "c1@example.com")
    booking_id = await _confirmed(
        committed_conn, seed["unit_type_id"], TODAY + dt.timedelta(days=30)
    )

    result = await payment_service.refund_booking(booking_id, conn=committed_conn)

    assert result["status"] == "refunded"
    assert result["free_cancelled"] is True


@pytest.mark.asyncio
async def test_late_cancellation_flagged(committed_conn) -> None:
    """Cancelling on the check-in day is past the free deadline."""
    seed = await _seed(committed_conn, "c2@example.com")
    booking_id = await _confirmed(committed_conn, seed["unit_type_id"], TODAY)

    result = await payment_service.refund_booking(booking_id, conn=committed_conn)

    assert result["status"] == "refunded"
    assert result["free_cancelled"] is False


# ---------------------------------------------------------------- commission


@pytest.mark.asyncio
async def test_commission_accrued_on_confirm(committed_conn) -> None:
    seed = await _seed(committed_conn, "c3@example.com")
    booking_id = await _confirmed(
        committed_conn, seed["unit_type_id"], TODAY + dt.timedelta(days=10)
    )

    row = await committed_conn.fetchrow(
        "SELECT commission_status, commission_amt::float8, total_amount::float8 "
        "FROM booking WHERE id = $1",
        booking_id,
    )
    assert row["commission_status"] == "accrued"
    # default 12% from legal config
    assert round(row["commission_amt"], 2) == round(row["total_amount"] * 0.12, 2)


@pytest.mark.asyncio
async def test_commission_voided_on_refund(committed_conn) -> None:
    seed = await _seed(committed_conn, "c4@example.com")
    booking_id = await _confirmed(
        committed_conn, seed["unit_type_id"], TODAY + dt.timedelta(days=10)
    )

    await payment_service.refund_booking(booking_id, conn=committed_conn)

    status = await committed_conn.fetchval(
        "SELECT commission_status FROM booking WHERE id = $1", booking_id
    )
    assert status == "void"


@pytest.mark.asyncio
async def test_commission_report_aggregates_per_partner(committed_conn) -> None:
    seed = await _seed(committed_conn, "c5@example.com")
    await _confirmed(committed_conn, seed["unit_type_id"], TODAY + dt.timedelta(days=10), nights=3)
    await _confirmed(committed_conn, seed["unit_type_id"], TODAY + dt.timedelta(days=20), nights=2)

    rep = await report.commission_report(committed_conn)

    assert rep["total"]["bookings"] == 2
    assert rep["total"]["gross"] == 15000  # 5 nights x 3000
    assert round(rep["total"]["commission"], 2) == round(15000 * 0.12, 2)
    assert len(rep["partners"]) == 1
    assert rep["partners"][0]["bookings"] == 2


@pytest.mark.asyncio
async def test_commission_report_excludes_refunded(committed_conn) -> None:
    """A refunded booking must not count towards commission."""
    seed = await _seed(committed_conn, "c6@example.com")
    keep = await _confirmed(
        committed_conn, seed["unit_type_id"], TODAY + dt.timedelta(days=10), nights=2
    )
    drop = await _confirmed(
        committed_conn, seed["unit_type_id"], TODAY + dt.timedelta(days=20), nights=2
    )
    await payment_service.refund_booking(drop, conn=committed_conn)

    rep = await report.commission_report(committed_conn)

    assert rep["total"]["bookings"] == 1
    assert rep["total"]["gross"] == 6000
    assert rep["partners"][0]["bookings"] == 1
    # the kept booking is the accrued one
    kept_id = await committed_conn.fetchval(
        "SELECT id::text FROM booking WHERE commission_status = 'accrued'"
    )
    assert kept_id == keep


@pytest.mark.asyncio
async def test_commission_report_date_filter(committed_conn) -> None:
    seed = await _seed(committed_conn, "c7@example.com")
    await _confirmed(committed_conn, seed["unit_type_id"], TODAY + dt.timedelta(days=10))
    await _confirmed(committed_conn, seed["unit_type_id"], TODAY + dt.timedelta(days=40))

    rep = await report.commission_report(
        committed_conn, TODAY + dt.timedelta(days=5), TODAY + dt.timedelta(days=30)
    )

    assert rep["total"]["bookings"] == 1
