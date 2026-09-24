"""Slice 2 tests: inventory generation + availability."""

from __future__ import annotations

import datetime as dt

import asyncpg
import pytest

from app.modules.auth import service as auth_service
from app.modules.auth.schemas import PartnerRegisterRequest
from app.modules.inventory import service
from app.modules.property import service as property_service
from app.modules.property.schemas import PropertyCreate


async def _setup_unit_type(conn: asyncpg.Connection, email: str) -> str:
    """Create a partner + property + unit_type, return unit_type id."""
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
        "INSERT INTO unit_type (property_id, name, capacity, total_units) "
        "VALUES ($1, 'Стандарт', 2, 3) RETURNING id::text",
        prop.id,
    )
    assert row is not None
    return row["id"]


# ---------------------------------------------------------------- generate


@pytest.mark.asyncio
async def test_generate_creates_horizon(db_conn) -> None:
    ut = await _setup_unit_type(db_conn, "inv1@example.com")
    inserted = await service.ensure_inventory(db_conn, ut, horizon_days=10)

    assert inserted == 10

    count = await db_conn.fetchval("SELECT count(*) FROM inventory_day WHERE unit_type_id=$1", ut)
    assert count == 10


@pytest.mark.asyncio
async def test_generate_is_idempotent(db_conn) -> None:
    """Running twice must not duplicate or overwrite rows."""
    ut = await _setup_unit_type(db_conn, "inv2@example.com")

    first = await service.ensure_inventory(db_conn, ut, horizon_days=10)
    second = await service.ensure_inventory(db_conn, ut, horizon_days=10)

    assert first == 10
    assert second == 0

    count = await db_conn.fetchval("SELECT count(*) FROM inventory_day WHERE unit_type_id=$1", ut)
    assert count == 10


@pytest.mark.asyncio
async def test_generated_rows_match_total_units(db_conn) -> None:
    ut = await _setup_unit_type(db_conn, "inv3@example.com")
    await service.ensure_inventory(db_conn, ut, horizon_days=5)

    rows = await db_conn.fetch(
        "SELECT available, hold, sold, closed FROM inventory_day WHERE unit_type_id=$1", ut
    )
    assert len(rows) == 5
    for r in rows:
        assert r["available"] == 3  # total_units
        assert r["hold"] == 0
        assert r["sold"] == 0
        assert r["closed"] is False


# ---------------------------------------------------------------- close


@pytest.mark.asyncio
async def test_close_range_marks_closed(db_conn) -> None:
    ut = await _setup_unit_type(db_conn, "inv4@example.com")
    today = dt.date.today()
    await service.ensure_inventory(db_conn, ut, horizon_days=10)

    affected = await service.close_range(
        db_conn, ut, today, today + dt.timedelta(days=3), closed=True
    )

    assert affected == 3  # [today, today+3) = 3 nights
    closed = await db_conn.fetchval(
        "SELECT count(*) FROM inventory_day WHERE unit_type_id=$1 AND closed", ut
    )
    assert closed == 3


@pytest.mark.asyncio
async def test_close_invalid_range_raises(db_conn) -> None:
    ut = await _setup_unit_type(db_conn, "inv5@example.com")
    today = dt.date.today()
    with pytest.raises(ValueError):
        await service.close_range(db_conn, ut, today, today)


# ---------------------------------------------------------------- availability


@pytest.mark.asyncio
async def test_availability_half_open_interval(db_conn) -> None:
    """A checkout on date_to is not a stay, so that night is excluded."""
    ut = await _setup_unit_type(db_conn, "inv6@example.com")
    today = dt.date.today()
    await service.ensure_inventory(db_conn, ut, horizon_days=10)

    days = await service.get_availability(db_conn, ut, today, today + dt.timedelta(days=5))

    assert len(days) == 5
    assert all(d["free"] == 3 for d in days)


@pytest.mark.asyncio
async def test_availability_reflects_closed(db_conn) -> None:
    ut = await _setup_unit_type(db_conn, "inv7@example.com")
    today = dt.date.today()
    await service.ensure_inventory(db_conn, ut, horizon_days=10)
    await service.close_range(db_conn, ut, today, today + dt.timedelta(days=2))

    days = await service.get_availability(db_conn, ut, today, today + dt.timedelta(days=4))

    assert days[0]["closed"] is True
    assert days[1]["closed"] is True
    assert days[2]["closed"] is False
    assert days[3]["closed"] is False


@pytest.mark.asyncio
async def test_availability_missing_days_excluded(db_conn) -> None:
    """Dates without inventory rows are simply absent from the result."""
    ut = await _setup_unit_type(db_conn, "inv8@example.com")
    today = dt.date.today()

    days = await service.get_availability(db_conn, ut, today, today + dt.timedelta(days=3))
    assert days == []


@pytest.mark.asyncio
async def test_availability_invalid_range_raises(db_conn) -> None:
    ut = await _setup_unit_type(db_conn, "inv9@example.com")
    today = dt.date.today()
    with pytest.raises(ValueError):
        await service.get_availability(db_conn, ut, today, today)
