"""iCal import tests: parsing, applying blocks, and the ownership invariants.

The critical invariants this slice guards:
  1. An imported block never cancels or overwrites a paid booking.
  2. The importer only unblocks what it blocked itself - a partner's manual
     stop sell survives import untouched.
"""

from __future__ import annotations

import datetime as dt
import uuid

import asyncpg
import httpx
import pytest

from app.modules.auth import service as auth_service
from app.modules.auth.schemas import PartnerRegisterRequest
from app.modules.booking import service as booking_service
from app.modules.property import service as property_service
from app.modules.property.schemas import PropertyCreate
from app.modules.sync import ical_import
from app.modules.sync.ical_parser import IcalParseError, parse_calendar

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
    return {"unit_type_id": row["id"], "partner_id": str(partner_id)}


def _guest() -> dict:
    return {
        "guest_name": "Иван Гость",
        "guest_email": f"g{uuid.uuid4().hex[:6]}@example.com",
        "guest_phone": "+79991234567",
    }


# ---------------------------------------------------------------- parser


def _cal(body: str) -> str:
    return "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID://t//t//RU\r\n" + body + "END:VCALENDAR\r\n"


def test_parser_reads_date_event() -> None:
    events = parse_calendar(
        _cal(
            "BEGIN:VEVENT\r\nUID:abc\r\nDTSTART;VALUE=DATE:20260110\r\n"
            "DTEND;VALUE=DATE:20260112\r\nSUMMARY:Busy\r\nEND:VEVENT\r\n"
        )
    )
    assert len(events) == 1
    assert events[0].uid == "abc"
    assert events[0].start == dt.date(2026, 1, 10)
    assert events[0].end == dt.date(2026, 1, 12)


def test_parser_unfolds_lines() -> None:
    events = parse_calendar(
        _cal(
            "BEGIN:VEVENT\r\nUID:abc\r\nSUMMARY:Long\r\n  Folded\r\n"
            "DTSTART;VALUE=DATE:20260110\r\nEND:VEVENT\r\n"
        )
    )
    assert events[0].summary == "Long Folded"


def test_parser_defaults_missing_dtend_to_one_night() -> None:
    events = parse_calendar(
        _cal("BEGIN:VEVENT\r\nUID:abc\r\nDTSTART;VALUE=DATE:20260110\r\nEND:VEVENT\r\n")
    )
    assert events[0].end == dt.date(2026, 1, 11)


def test_parser_accepts_datetime_form() -> None:
    events = parse_calendar(
        _cal(
            "BEGIN:VEVENT\r\nUID:abc\r\nDTSTART:20260110T140000Z\r\n"
            "DTEND:20260112T100000Z\r\nEND:VEVENT\r\n"
        )
    )
    assert events[0].start == dt.date(2026, 1, 10)
    assert events[0].end == dt.date(2026, 1, 12)


def test_parser_expands_daily_rrule_with_count() -> None:
    events = parse_calendar(
        _cal(
            "BEGIN:VEVENT\r\nUID:abc\r\nDTSTART;VALUE=DATE:20260110\r\n"
            "DTEND;VALUE=DATE:20260111\r\nRRULE:FREQ=DAILY;COUNT=3\r\nEND:VEVENT\r\n"
        )
    )
    # 3 one-night instances: 10, 11, 12 -> span covers [10, 13)
    assert events[0].start == dt.date(2026, 1, 10)
    assert events[0].end == dt.date(2026, 1, 13)


def test_parser_rejects_unbounded_rrule() -> None:
    with pytest.raises(IcalParseError):
        parse_calendar(
            _cal(
                "BEGIN:VEVENT\r\nUID:abc\r\nDTSTART;VALUE=DATE:20260110\r\n"
                "RRULE:FREQ=DAILY\r\nEND:VEVENT\r\n"
            )
        )


def test_parser_rejects_missing_dtstart() -> None:
    with pytest.raises(IcalParseError):
        parse_calendar(_cal("BEGIN:VEVENT\r\nUID:abc\r\nEND:VEVENT\r\n"))


# ---------------------------------------------------------------- apply


@pytest.mark.asyncio
async def test_apply_blocks_and_unblocks(db_conn) -> None:
    seed = await _seed(db_conn, "x1@example.com")
    ut = seed["unit_type_id"]

    result = await ical_import.apply_import(
        db_conn, ut, {TODAY + dt.timedelta(days=10), TODAY + dt.timedelta(days=11)}
    )
    assert result["blocked"] == 2

    closed = await db_conn.fetchval(
        "SELECT bool_and(closed) FROM inventory_day "
        "WHERE unit_type_id = $1 AND date >= $2 AND date < $3",
        ut,
        TODAY + dt.timedelta(days=10),
        TODAY + dt.timedelta(days=12),
    )
    assert closed is True
    source = await db_conn.fetchval(
        "SELECT closed_source FROM inventory_day WHERE unit_type_id = $1 AND date = $2",
        ut,
        TODAY + dt.timedelta(days=10),
    )
    assert source == "import"


@pytest.mark.asyncio
async def test_apply_unblocks_only_import_closures(db_conn) -> None:
    """The core invariant: manual stop sell survives import."""
    seed = await _seed(db_conn, "x2@example.com")
    ut = seed["unit_type_id"]

    # import closes +10 and +11, partner manually closes +20
    await ical_import.apply_import(
        db_conn, ut, {TODAY + dt.timedelta(days=10), TODAY + dt.timedelta(days=11)}
    )
    await db_conn.execute(
        "UPDATE inventory_day SET closed = true, closed_source = 'manual' "
        "WHERE unit_type_id = $1 AND date = $2",
        ut,
        TODAY + dt.timedelta(days=20),
    )

    # next sync: the feed no longer has +10 or +11
    result = await ical_import.apply_import(db_conn, ut, set())

    assert result["cleared"] == 2
    assert (
        await db_conn.fetchval(
            "SELECT closed FROM inventory_day WHERE unit_type_id = $1 AND date = $2",
            ut,
            TODAY + dt.timedelta(days=10),
        )
        is False
    )
    assert (
        await db_conn.fetchval(
            "SELECT closed FROM inventory_day WHERE unit_type_id = $1 AND date = $2",
            ut,
            TODAY + dt.timedelta(days=20),
        )
        is True
    )


@pytest.mark.asyncio
async def test_apply_creates_missing_inventory_rows(db_conn) -> None:
    """A feed may block dates the generator has not reached yet."""
    seed = await _seed(db_conn, "x3@example.com")
    ut = seed["unit_type_id"]
    await db_conn.execute("DELETE FROM inventory_day WHERE unit_type_id = $1", ut)

    far = TODAY + dt.timedelta(days=300)
    result = await ical_import.apply_import(db_conn, ut, {far})

    assert result["blocked"] == 1
    assert (
        await db_conn.fetchval(
            "SELECT closed FROM inventory_day WHERE unit_type_id = $1 AND date = $2",
            ut,
            far,
        )
        is True
    )


@pytest.mark.asyncio
async def test_import_never_touches_paid_bookings(db_conn) -> None:
    """Blocking a date with a confirmed booking closes it, but keeps the booking."""
    seed = await _seed(db_conn, "x4@example.com")
    ut = seed["unit_type_id"]

    booking = await booking_service.create_hold(
        db_conn,
        unit_type_id=ut,
        checkin=TODAY + dt.timedelta(days=10),
        checkout=TODAY + dt.timedelta(days=12),
        idempotency_key=f"k-{uuid.uuid4()}",
        **_guest(),
    )
    await db_conn.execute("UPDATE booking SET status = 'confirmed' WHERE id = $1", booking["id"])

    await ical_import.apply_import(
        db_conn, ut, {TODAY + dt.timedelta(days=10), TODAY + dt.timedelta(days=11)}
    )

    status = await db_conn.fetchval("SELECT status FROM booking WHERE id = $1", booking["id"])
    assert status == "confirmed"
    # and the date is now closed to NEW bookings
    assert (
        await db_conn.fetchval(
            "SELECT closed FROM inventory_day WHERE unit_type_id = $1 AND date = $2",
            ut,
            TODAY + dt.timedelta(days=10),
        )
        is True
    )


# ---------------------------------------------------------------- sync (HTTP mocked)


@pytest.mark.asyncio
async def test_sync_fetches_and_applies(db_conn, monkeypatch) -> None:
    seed = await _seed(db_conn, "x5@example.com")
    ut = seed["unit_type_id"]

    sub_id = await db_conn.fetchval(
        "INSERT INTO ical_subscription (unit_type_id, url) VALUES ($1, $2) RETURNING id::text",
        ut,
        "https://example.com/cal.ics",
    )
    body = _cal(
        "BEGIN:VEVENT\r\nUID:e1\r\nDTSTART;VALUE=DATE:"
        + (TODAY + dt.timedelta(days=5)).strftime("%Y%m%d")
        + "\r\nDTEND;VALUE=DATE:"
        + (TODAY + dt.timedelta(days=7)).strftime("%Y%m%d")
        + "\r\nSUMMARY:Blocked\r\nEND:VEVENT\r\n"
    )

    async def fake_fetch(url: str) -> str:
        assert url == "https://example.com/cal.ics"
        return body

    monkeypatch.setattr(ical_import, "_fetch", fake_fetch)

    result = await ical_import.sync_subscription(db_conn, sub_id)

    assert result["status"] == "ok"
    assert result["blocked"] == 2
    row = await db_conn.fetchrow(
        "SELECT last_status, last_blocked FROM ical_subscription WHERE id = $1",
        sub_id,
    )
    assert row["last_status"] == "ok"
    assert row["last_blocked"] == 2


@pytest.mark.asyncio
async def test_sync_records_fetch_errors(db_conn, monkeypatch) -> None:
    seed = await _seed(db_conn, "x6@example.com")
    sub_id = await db_conn.fetchval(
        "INSERT INTO ical_subscription (unit_type_id, url) VALUES ($1, $2) RETURNING id::text",
        seed["unit_type_id"],
        "https://example.com/cal.ics",
    )

    async def failing_fetch(url: str) -> str:
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(ical_import, "_fetch", failing_fetch)

    result = await ical_import.sync_subscription(db_conn, sub_id)

    assert result["status"] == "error"
    row = await db_conn.fetchrow(
        "SELECT last_status, last_error FROM ical_subscription WHERE id = $1",
        sub_id,
    )
    assert row["last_status"] == "error"
    assert "boom" in row["last_error"]
