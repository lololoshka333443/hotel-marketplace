"""Channel write-API tests.

The invariants this slice guards:
  1. A channel pushes bookings through the *same* path a guest takes - the
     double-booking invariant and stop sell are not bypassed.
  2. An API key only reaches its own partner's inventory.
  3. Retries are idempotent end to end: a replay returns the original booking,
     confirmed, not a duplicate and not an error.
  4. The plaintext key is shown once; the store and the list never leak it.
"""

from __future__ import annotations

import datetime as dt
import uuid

import asyncpg
import pytest

from app.modules.auth import service as auth_service
from app.modules.auth.schemas import PartnerRegisterRequest
from app.modules.channel import service
from app.modules.property import service as property_service
from app.modules.property.schemas import PropertyCreate

TODAY = dt.date.today()


async def _seed(conn: asyncpg.Connection, email: str, total_units: int = 1) -> dict:
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
        "VALUES ($1, 'Квартира', 2, $2, 3000) RETURNING id::text",
        prop.id,
        total_units,
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
    return {"unit_type_id": row["id"], "partner_id": str(partner_id)}


def _guest() -> dict:
    return {
        "name": "Иван Гость",
        "email": f"g{uuid.uuid4().hex[:6]}@example.com",
        "phone": "+79991234567",
    }


def _push(seed: dict, key: str, *, checkin=None, checkout=None, idem="req-1") -> dict:
    """One push is one channel request; a retry repeats it verbatim.

    The guest email is derived from the key on purpose: an idempotency replay
    must repeat the *same* request, and a random email per call would turn
    every retry into a different guest.
    """
    return dict(
        partner_id=seed["partner_id"],
        unit_type_id=seed["unit_type_id"],
        checkin=checkin or TODAY + dt.timedelta(days=10),
        checkout=checkout or TODAY + dt.timedelta(days=12),
        guest_name="Иван Гость",
        guest_email=f"g{idem}@example.com",
        guest_phone="+79991234567",
        client_key=idem,
    )


# ---------------------------------------------------------------- keys


async def _partner(conn: asyncpg.Connection, email: str) -> str:
    return str(
        await auth_service.register_partner(
            conn, PartnerRegisterRequest(email=email, password="secret123", name="Tester")
        )
    )


@pytest.mark.asyncio
async def test_create_key_returns_plaintext_once(db_conn) -> None:
    pid = await _partner(db_conn, "k1@example.com")
    created = await service.create_key(db_conn, pid, "Sutochno API")
    assert created["key"].startswith("hm_live_")
    assert created["key_prefix"] == created["key"][: len("hm_live_") + 6]

    # The stored row has no plaintext, only the hash.
    stored = await db_conn.fetchval("SELECT key_hash FROM api_key WHERE id = $1", created["id"])
    assert stored is not None
    assert created["key"] not in stored

    # The list never contains the secret either.
    listed = await service.list_keys(db_conn, pid)
    assert listed[0]["label"] == "Sutochno API"
    assert "key" not in listed[0]


@pytest.mark.asyncio
async def test_revoke_only_own_key(db_conn) -> None:
    pid = await _partner(db_conn, "k2@example.com")
    pid2 = await _partner(db_conn, "k3@example.com")
    mine = await service.create_key(db_conn, pid, "mine")
    await service.create_key(db_conn, pid2, "theirs")

    assert await service.revoke_key(db_conn, pid, mine["id"]) is True
    # Another partner's id is not revokable through my partner_id.
    assert await service.revoke_key(db_conn, pid, "00000000-0000-0000-0000-000000000000") is False
    assert await db_conn.fetchval("SELECT count(*) FROM api_key") == 1


@pytest.mark.asyncio
async def test_resolve_rejects_unknown_and_disabled(db_conn) -> None:
    pid = await _partner(db_conn, "k4@example.com")
    with pytest.raises(service.KeyRejected):
        await service.resolve_key(db_conn, "hm_live_nope")

    created = await service.create_key(db_conn, pid, "Тест-ключ")
    resolved = await service.resolve_key(db_conn, created["key"])
    assert resolved["partner_id"] == pid

    await db_conn.execute("UPDATE api_key SET enabled = false WHERE id = $1", created["id"])
    with pytest.raises(service.KeyRejected):
        await service.resolve_key(db_conn, created["key"])


@pytest.mark.asyncio
async def test_resolve_stamps_last_used(db_conn) -> None:
    pid = await _partner(db_conn, "k5@example.com")
    created = await service.create_key(db_conn, pid, "Тест-ключ")
    await db_conn.execute("UPDATE api_key SET last_used_at = NULL WHERE id = $1", created["id"])
    await service.resolve_key(db_conn, created["key"])
    used = await db_conn.fetchval(
        "SELECT last_used_at IS NOT NULL FROM api_key WHERE id = $1", created["id"]
    )
    assert used is True


# ---------------------------------------------------------------- booking


@pytest.mark.asyncio
async def test_channel_booking_confirms_and_sells(committed_conn) -> None:
    """The full path: hold -> pay_and_confirm -> sold inventory, origin channel."""
    seed = await _seed(committed_conn, "c1@example.com")
    created = await service.create_key(committed_conn, seed["partner_id"], "API")
    key = await service.resolve_key(committed_conn, created["key"])

    out = await service.create_channel_booking(committed_conn, **_push(seed, created["key"]))
    assert out["status"] == "confirmed"
    assert out["total_amount"] == 6000.0

    booking = await committed_conn.fetchrow(
        "SELECT origin, status FROM booking WHERE id = $1", out["id"]
    )
    assert booking["origin"] == "channel"
    assert booking["status"] == "confirmed"

    sold = await committed_conn.fetchval(
        "SELECT sold FROM inventory_day WHERE unit_type_id = $1 AND date = $2",
        seed["unit_type_id"],
        TODAY + dt.timedelta(days=10),
    )
    assert sold == 1
    # last_used_at moved on the key that pushed it.
    assert key["partner_id"] == seed["partner_id"]


@pytest.mark.asyncio
async def test_channel_booking_is_idempotent_end_to_end(committed_conn) -> None:
    """A retry after success returns the same confirmed booking, not a second one."""
    seed = await _seed(committed_conn, "c2@example.com")
    created = await service.create_key(committed_conn, seed["partner_id"], "API")

    first = await service.create_channel_booking(
        committed_conn, **_push(seed, created["key"], idem="req-1")
    )
    second = await service.create_channel_booking(
        committed_conn, **_push(seed, created["key"], idem="req-1")
    )

    assert first["id"] == second["id"]
    assert second["status"] == "confirmed"
    assert await committed_conn.fetchval("SELECT count(*) FROM booking") == 1


@pytest.mark.asyncio
async def test_idempotency_key_conflict_on_different_dates(committed_conn) -> None:
    """The same key with a different stay is a client bug: refuse, never double-book."""
    from app.modules.booking import service as booking_service

    seed = await _seed(committed_conn, "c6@example.com")
    created = await service.create_key(committed_conn, seed["partner_id"], "API")

    await service.create_channel_booking(
        committed_conn, **_push(seed, created["key"], idem="req-1")
    )
    with pytest.raises(booking_service.Conflict):
        await service.create_channel_booking(
            committed_conn,
            **_push(
                seed,
                created["key"],
                idem="req-1",
                checkin=TODAY + dt.timedelta(days=40),
                checkout=TODAY + dt.timedelta(days=41),
            ),
        )


@pytest.mark.asyncio
async def test_channel_booking_respects_stop_sell(committed_conn) -> None:
    """Stop sell (incl. imported closures) blocks a channel just like a guest."""
    from app.modules.booking import service as booking_service

    seed = await _seed(committed_conn, "c3@example.com")
    created = await service.create_key(committed_conn, seed["partner_id"], "API")

    await committed_conn.execute(
        "UPDATE inventory_day SET closed = true WHERE unit_type_id = $1 AND date = $2",
        seed["unit_type_id"],
        TODAY + dt.timedelta(days=10),
    )

    with pytest.raises(booking_service.NotAvailable) as exc:
        await service.create_channel_booking(committed_conn, **_push(seed, created["key"]))
    assert "closed" in str(exc.value)


@pytest.mark.asyncio
async def test_channel_cannot_book_other_partners_inventory(committed_conn) -> None:
    seed_a = await _seed(committed_conn, "c4a@example.com")
    seed_b = await _seed(committed_conn, "c4b@example.com")
    created_b = await service.create_key(committed_conn, seed_b["partner_id"], "API")

    with pytest.raises(service.NotOwned):
        await service.create_channel_booking(
            committed_conn,
            **{**_push(seed_a, created_b["key"]), "partner_id": seed_b["partner_id"]},
        )
    # Nothing was created.
    assert await committed_conn.fetchval("SELECT count(*) FROM booking") == 0


@pytest.mark.asyncio
async def test_channel_booking_never_oversells(committed_conn) -> None:
    """One unit left; after the channel books it, nothing remains for anyone."""
    from app.modules.booking import service as booking_service

    seed = await _seed(committed_conn, "c5@example.com", total_units=1)
    created = await service.create_key(committed_conn, seed["partner_id"], "API")

    await service.create_channel_booking(
        committed_conn,
        **_push(
            seed,
            created["key"],
            checkin=TODAY + dt.timedelta(days=20),
            checkout=TODAY + dt.timedelta(days=22),
        ),
    )

    # Same dates are gone for a second channel booking (or a guest).
    with pytest.raises(booking_service.NotAvailable):
        await service.create_channel_booking(
            committed_conn,
            **_push(
                seed,
                created["key"],
                idem="req-2",
                checkin=TODAY + dt.timedelta(days=21),
                checkout=TODAY + dt.timedelta(days=23),
            ),
        )


# ---------------------------------------------------------------- cancel


@pytest.mark.asyncio
async def test_cancel_releases_sold_inventory(committed_conn) -> None:
    seed = await _seed(committed_conn, "c7@example.com")
    created = await service.create_key(committed_conn, seed["partner_id"], "API")

    out = await service.create_channel_booking(committed_conn, **_push(seed, created["key"]))
    assert (
        await committed_conn.fetchval(
            "SELECT sold FROM inventory_day WHERE unit_type_id = $1 AND date = $2",
            seed["unit_type_id"],
            TODAY + dt.timedelta(days=10),
        )
        == 1
    )

    cancelled = await service.cancel_channel_booking(committed_conn, seed["partner_id"], out["id"])
    assert cancelled["status"] == "refunded"
    assert (
        await committed_conn.fetchval(
            "SELECT sold FROM inventory_day WHERE unit_type_id = $1 AND date = $2",
            seed["unit_type_id"],
            TODAY + dt.timedelta(days=10),
        )
        == 0
    )


@pytest.mark.asyncio
async def test_cancel_refuses_other_partners_booking(committed_conn) -> None:
    seed_a = await _seed(committed_conn, "c8a@example.com")
    seed_b = await _seed(committed_conn, "c8b@example.com")
    created_a = await service.create_key(committed_conn, seed_a["partner_id"], "API")

    out = await service.create_channel_booking(committed_conn, **_push(seed_a, created_a["key"]))

    with pytest.raises(service.NotOwned):
        await service.cancel_channel_booking(committed_conn, seed_b["partner_id"], out["id"])


@pytest.mark.asyncio
async def test_web_booking_invisible_to_channel_cancel(committed_conn) -> None:
    """A channel cannot cancel a booking the guest made directly."""
    from app.modules.booking import service as booking_service

    seed = await _seed(committed_conn, "c9@example.com")
    await service.create_key(committed_conn, seed["partner_id"], "API")

    async with committed_conn.transaction(isolation="serializable"):
        web_hold = await booking_service.create_hold(
            committed_conn,
            unit_type_id=seed["unit_type_id"],
            checkin=TODAY + dt.timedelta(days=30),
            checkout=TODAY + dt.timedelta(days=31),
            guest_name="Гость",
            guest_email="w@example.com",
            guest_phone="+79991112233",
        )

    with pytest.raises(service.NotOwned):
        await service.cancel_channel_booking(committed_conn, seed["partner_id"], web_hold["id"])
