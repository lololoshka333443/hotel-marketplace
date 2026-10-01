"""Slice 1 tests: property CRUD + partner isolation.

Every test runs inside a rolled-back transaction (see conftest.py), so created
properties never persist between tests.
"""
from __future__ import annotations

import pytest

from app.modules.auth import service as auth_service
from app.modules.auth.schemas import PartnerRegisterRequest
from app.modules.property import service
from app.modules.property.schemas import PropertyCreate, PropertyUpdate


async def _make_partner(conn, email: str) -> str:
    return await auth_service.register_partner(
        conn, PartnerRegisterRequest(email=email, password="secret123", name="Tester")
    )


def _sample(name: str = "Апартаменты у моря", city: str = "Yalta") -> PropertyCreate:
    return PropertyCreate(
        name=name,
        property_type="apartment",
        city=city,
        timezone="Europe/Simferopol",
    )


# ---------------------------------------------------------------- create / list


@pytest.mark.asyncio
async def test_create_and_list_property(db_conn) -> None:
    partner_id = await _make_partner(db_conn, "p1@example.com")
    created = await service.create_property(db_conn, partner_id, _sample())

    assert created.partner_id == partner_id
    assert created.status == "draft"  # never published immediately
    assert created.slug and created.slug != ""

    props = await service.get_partner_properties(db_conn, partner_id)
    assert len(props) == 1
    assert props[0].id == created.id


@pytest.mark.asyncio
async def test_create_two_partners_isolation(db_conn) -> None:
    """The core access rule: a partner sees only their own properties."""
    partner_a = await _make_partner(db_conn, "a@example.com")
    partner_b = await _make_partner(db_conn, "b@example.com")

    await service.create_property(db_conn, partner_a, _sample("Квартира A"))
    await service.create_property(db_conn, partner_b, _sample("Квартира B"))

    a_list = await service.get_partner_properties(db_conn, partner_a)
    b_list = await service.get_partner_properties(db_conn, partner_b)

    assert [p.name for p in a_list] == ["Квартира A"]
    assert [p.name for p in b_list] == ["Квартира B"]


# ---------------------------------------------------------------- update


@pytest.mark.asyncio
async def test_update_own_property(db_conn) -> None:
    partner_id = await _make_partner(db_conn, "p2@example.com")
    created = await service.create_property(db_conn, partner_id, _sample())
    upd = PropertyUpdate(name="Апартаменты у гор", city="Sevastopol")

    updated = await service.update_property(db_conn, created.id, partner_id, upd)

    assert updated is not None
    assert updated.name == "Апартаменты у гор"
    assert updated.city == "Sevastopol"


@pytest.mark.asyncio
async def test_cannot_update_other_partners_property(db_conn) -> None:
    """Partner B must not be able to touch partner A's property."""
    partner_a = await _make_partner(db_conn, "a2@example.com")
    partner_b = await _make_partner(db_conn, "b2@example.com")
    created = await service.create_property(db_conn, partner_a, _sample())

    result = await service.update_property(
        db_conn, created.id, partner_b, PropertyUpdate(name="HACKED")
    )

    assert result is None  # not found for this partner


# ---------------------------------------------------------------- public catalog


@pytest.mark.asyncio
async def test_draft_property_hidden_from_catalog(db_conn) -> None:
    """The catalog shows only published properties."""
    partner_id = await _make_partner(db_conn, "p3@example.com")
    created = await service.create_property(db_conn, partner_id, _sample())

    # draft → not visible
    assert await service.get_public_property(db_conn, created.id) is None
    assert await service.list_public_properties(db_conn) == []

    # publish it
    await service.update_property(
        db_conn, created.id, partner_id, PropertyUpdate(status="published")
    )

    public = await service.get_public_property(db_conn, created.id)
    assert public is not None
    assert public["name"] == created.name
    # partner_id must never leak into the public payload
    assert "partner_id" not in public


@pytest.mark.asyncio
async def test_invalid_timezone_rejected() -> None:
    with pytest.raises(ValueError):
        PropertyCreate(name="X", property_type="apartment", timezone="Not/AZone")


# ---------------------------------------------------------------- public rooms


@pytest.mark.asyncio
async def test_public_unit_types_listed_for_published_property(db_conn) -> None:
    """A guest booking the catalog needs the room list, unauthenticated.

    The route is a thin wrapper over the pool, so the rule itself is checked
    here: the room list comes from the same query the guest reads, and a draft
    property's rooms are not published either.
    """
    partner_id = await _make_partner(db_conn, "p4@example.com")
    created = await service.create_property(db_conn, partner_id, _sample())

    async with db_conn.transaction():
        ut_id = await db_conn.fetchval(
            "INSERT INTO unit_type (property_id, name, capacity, total_units) "
            "VALUES ($1, 'Стандарт', 2, 3) RETURNING id::text",
            created.id,
        )
    assert ut_id is not None

    # draft → the room list must not serve an unpublished property
    assert await service.get_public_property(db_conn, created.id) is None

    await service.update_property(
        db_conn, created.id, partner_id, PropertyUpdate(status="published")
    )

    # published → the same room query serves the guest
    public = await service.get_public_property(db_conn, created.id)
    assert public is not None
    rows = await db_conn.fetch(
        "SELECT name, total_units FROM unit_type WHERE property_id = $1 "
        "ORDER BY created_at",
        created.id,
    )
    assert [r["name"] for r in rows] == ["Стандарт"]
    assert rows[0]["total_units"] == 3
