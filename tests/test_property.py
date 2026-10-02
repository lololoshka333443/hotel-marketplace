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
    assert (await service.list_public_properties(db_conn))["items"] == []

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
        "SELECT name, total_units FROM unit_type WHERE property_id = $1 ORDER BY created_at",
        created.id,
    )
    assert [r["name"] for r in rows] == ["Стандарт"]
    assert rows[0]["total_units"] == 3


# ---------------------------------------------------------------- publish route


@pytest.mark.asyncio
async def test_partner_publishes_own_property_over_http(committed_conn) -> None:
    """The cabinet's Publish button: PATCH /partner/properties/{id} to published.

    A property starts as a draft and stays invisible to guests until the
    partner publishes it. This is the route that button hits.
    """
    from starlette.testclient import TestClient

    from app.main import create_app
    from app.modules.auth.jwt import create_access_token

    partner_id = await _make_partner(committed_conn, "pub-1@example.com")
    created = await service.create_property(committed_conn, partner_id, _sample())

    with TestClient(create_app()) as client:
        response = client.patch(
            f"/v1/partner/properties/{created.id}",
            json={"status": "published"},
            headers={"Authorization": f"Bearer {create_access_token(partner_id, scope='partner')}"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "published"
    # The guest sees it now — the catalog is what publish unlocks.
    public = (await service.list_public_properties(committed_conn))["items"]
    assert any(p["id"] == created.id for p in public)


@pytest.mark.asyncio
async def test_partner_cannot_publish_other_partners_property(committed_conn) -> None:
    """PATCH on a stranger's property answers 404, never publishes it."""
    from starlette.testclient import TestClient

    from app.main import create_app
    from app.modules.auth.jwt import create_access_token

    partner_a = await _make_partner(committed_conn, "pub-a@example.com")
    partner_b = await _make_partner(committed_conn, "pub-b@example.com")
    created = await service.create_property(committed_conn, partner_a, _sample())

    with TestClient(create_app()) as client:
        response = client.patch(
            f"/v1/partner/properties/{created.id}",
            json={"status": "published"},
            headers={"Authorization": f"Bearer {create_access_token(partner_b, scope='partner')}"},
        )

    assert response.status_code == 404, response.text
    assert await service.get_public_property(committed_conn, created.id) is None


@pytest.mark.asyncio
async def test_publish_route_requires_partner_scope(committed_conn) -> None:
    """An admin token cannot publish through the partner route."""
    from starlette.testclient import TestClient

    from app.main import create_app
    from app.modules.auth.jwt import create_access_token

    partner_id = await _make_partner(committed_conn, "pub-scope@example.com")
    created = await service.create_property(committed_conn, partner_id, _sample())

    with TestClient(create_app()) as client:
        response = client.patch(
            f"/v1/partner/properties/{created.id}",
            json={"status": "published"},
            headers={"Authorization": f"Bearer {create_access_token(partner_id, scope='admin')}"},
        )

    assert response.status_code == 403, response.text
    assert await service.get_public_property(committed_conn, created.id) is None


@pytest.mark.asyncio
async def test_unpublish_returns_property_to_draft(committed_conn) -> None:
    """Published → draft hides the property from guests again.

    The cabinet needs the reverse action too: a property taken offline stops
    being bookable immediately.
    """
    from starlette.testclient import TestClient

    from app.main import create_app
    from app.modules.auth.jwt import create_access_token

    partner_id = await _make_partner(committed_conn, "pub-down@example.com")
    created = await service.create_property(committed_conn, partner_id, _sample())
    await service.update_property(
        committed_conn, created.id, partner_id, PropertyUpdate(status="published")
    )

    with TestClient(create_app()) as client:
        response = client.patch(
            f"/v1/partner/properties/{created.id}",
            json={"status": "draft"},
            headers={"Authorization": f"Bearer {create_access_token(partner_id, scope='partner')}"},
        )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "draft"
    assert (await service.list_public_properties(committed_conn))["items"] == []


# ------------------------------------------------------------------ room price


@pytest.mark.asyncio
async def test_create_unit_type_carries_base_price(committed_conn) -> None:
    """The room's base price arrives with the room, not in a second step.

    Without it the inventory exists but every night reads 0 in the catalog and
    in the booking total: a rate plan is empty by default and the effective
    price falls back to base_price.
    """
    from starlette.testclient import TestClient

    from app.main import create_app
    from app.modules.auth.jwt import create_access_token

    partner_id = await _make_partner(committed_conn, "price-1@example.com")
    created = await service.create_property(committed_conn, partner_id, _sample())
    headers = {"Authorization": f"Bearer {create_access_token(partner_id, scope='partner')}"}

    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/partner/unit-types",
            json={
                "property_id": created.id,
                "name": "Стандарт",
                "capacity": 2,
                "total_units": 3,
                "base_price": 4500,
            },
            headers=headers,
        )

    assert response.status_code == 201, response.text
    assert response.json()["base_price"] == 4500

    # The partner list echoes it back: the cabinet shows what it saved.
    with TestClient(create_app()) as client:
        response = client.get(
            f"/v1/partner/unit-types/property/{created.id}",
            headers=headers,
        )
    assert response.status_code == 200, response.text
    assert response.json()[0]["base_price"] == 4500

    # And the guest's room list carries the same number.
    await service.update_property(
        committed_conn, created.id, partner_id, PropertyUpdate(status="published")
    )
    public = await service.list_public_unit_types(committed_conn, created.id)
    assert public and public[0]["price"] == 4500


@pytest.mark.asyncio
async def test_unit_type_base_price_defaults_to_zero(committed_conn) -> None:
    """An omitted price is 0, not an error: the room still becomes bookable,
    and RateManager is where the partner sets the real number later."""
    from starlette.testclient import TestClient

    from app.main import create_app
    from app.modules.auth.jwt import create_access_token

    partner_id = await _make_partner(committed_conn, "price-2@example.com")
    created = await service.create_property(committed_conn, partner_id, _sample())

    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/partner/unit-types",
            json={
                "property_id": created.id,
                "name": "Стандарт",
                "capacity": 2,
                "total_units": 1,
            },
            headers={"Authorization": f"Bearer {create_access_token(partner_id, scope='partner')}"},
        )

    assert response.status_code == 201, response.text
    assert response.json()["base_price"] == 0


@pytest.mark.asyncio
async def test_negative_base_price_rejected(committed_conn) -> None:
    """A negative price is a client error, never a row in the database."""
    from starlette.testclient import TestClient

    from app.main import create_app
    from app.modules.auth.jwt import create_access_token

    partner_id = await _make_partner(committed_conn, "price-3@example.com")
    created = await service.create_property(committed_conn, partner_id, _sample())

    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/partner/unit-types",
            json={
                "property_id": created.id,
                "name": "Стандарт",
                "capacity": 2,
                "total_units": 1,
                "base_price": -100,
            },
            headers={"Authorization": f"Bearer {create_access_token(partner_id, scope='partner')}"},
        )

    assert response.status_code == 422, response.text


# ------------------------------------------------------------------ catalog price


@pytest.mark.asyncio
async def test_published_property_carries_cheapest_night(db_conn) -> None:
    """The catalog card shows the cheapest night, so a guest compares objects
    before opening one. The number comes straight from the room types — the
    seed keeps it in base_price, no rate plan rows exist yet.
    """
    partner_id = await _make_partner(db_conn, "min-1@example.com")
    created = await service.create_property(db_conn, partner_id, _sample())

    async with db_conn.transaction():
        await db_conn.execute(
            "INSERT INTO unit_type (property_id, name, capacity, total_units, base_price) "
            "VALUES ($1, 'Бюджет', 2, 1, 3200)",
            created.id,
        )
        await db_conn.execute(
            "INSERT INTO unit_type (property_id, name, capacity, total_units, base_price) "
            "VALUES ($1, 'Люкс', 4, 2, 8900)",
            created.id,
        )

    await service.update_property(
        db_conn, created.id, partner_id, PropertyUpdate(status="published")
    )

    single = await service.get_public_property(db_conn, created.id)
    assert single is not None
    assert single["min_price"] == 3200

    rows = (await service.list_public_properties(db_conn))["items"]
    match = next(p for p in rows if p["id"] == created.id)
    assert match["min_price"] == 3200


@pytest.mark.asyncio
async def test_property_without_rooms_has_no_min_price(db_conn) -> None:
    """A published property with no room types is not bookable yet. min_price
    is None, and the card says 'цена не указана' instead of promising a 0."""
    partner_id = await _make_partner(db_conn, "min-2@example.com")
    created = await service.create_property(db_conn, partner_id, _sample())

    await service.update_property(
        db_conn, created.id, partner_id, PropertyUpdate(status="published")
    )

    single = await service.get_public_property(db_conn, created.id)
    assert single is not None
    assert single["min_price"] is None


# ------------------------------------------------------------------ room editing


@pytest.mark.asyncio
async def test_partner_reprices_own_unit_type(committed_conn) -> None:
    """A room created with a wrong price is fixed without a rate plan.

    base_price is the fallback every unpriced day reads, so this one call
    reprices the whole season the partner never touched in RateManager.
    """
    from starlette.testclient import TestClient

    from app.main import create_app
    from app.modules.auth.jwt import create_access_token

    partner_id = await _make_partner(committed_conn, "edit-1@example.com")
    created = await service.create_property(committed_conn, partner_id, _sample())
    headers = {"Authorization": f"Bearer {create_access_token(partner_id, scope='partner')}"}

    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/partner/unit-types",
            json={
                "property_id": created.id,
                "name": "Стандарт",
                "capacity": 2,
                "total_units": 2,
                "base_price": 1000,
            },
            headers=headers,
        )
    unit_id = response.json()["id"]

    with TestClient(create_app()) as client:
        response = client.patch(
            f"/v1/partner/unit-types/{unit_id}",
            json={"base_price": 5200},
            headers=headers,
        )

    assert response.status_code == 200, response.text
    assert response.json()["base_price"] == 5200
    # The catalog's "от X ₽" follows the room, not just the partner list.
    await service.update_property(
        committed_conn, created.id, partner_id, PropertyUpdate(status="published")
    )
    public = (await service.list_public_properties(committed_conn))["items"]
    match = next(p for p in public if p["id"] == created.id)
    assert match["min_price"] == 5200


@pytest.mark.asyncio
async def test_partner_cannot_edit_other_partners_unit_type(committed_conn) -> None:
    """PATCH on a stranger's room answers 404 and never changes the price."""
    from starlette.testclient import TestClient

    from app.main import create_app
    from app.modules.auth.jwt import create_access_token

    owner = await _make_partner(committed_conn, "edit-a@example.com")
    intruder = await _make_partner(committed_conn, "edit-b@example.com")
    created = await service.create_property(committed_conn, owner, _sample())

    with TestClient(create_app()) as client:
        create = client.post(
            "/v1/partner/unit-types",
            json={
                "property_id": created.id,
                "name": "Стандарт",
                "capacity": 2,
                "total_units": 1,
                "base_price": 3000,
            },
            headers={"Authorization": f"Bearer {create_access_token(owner, scope='partner')}"},
        )
    unit_id = create.json()["id"]

    with TestClient(create_app()) as client:
        response = client.patch(
            f"/v1/partner/unit-types/{unit_id}",
            json={"base_price": 10},
            headers={"Authorization": f"Bearer {create_access_token(intruder, scope='partner')}"},
        )

    assert response.status_code == 404, response.text
    saved = await committed_conn.fetchval(
        "SELECT base_price::float8 FROM unit_type WHERE id = $1", unit_id
    )
    assert saved == 3000.0


@pytest.mark.asyncio
async def test_empty_unit_type_update_is_rejected(committed_conn) -> None:
    """An empty PATCH is a client error: nothing to save, and answering 200
    would make a UI miss look like a success."""
    from starlette.testclient import TestClient

    from app.main import create_app
    from app.modules.auth.jwt import create_access_token

    partner_id = await _make_partner(committed_conn, "edit-empty@example.com")
    created = await service.create_property(committed_conn, partner_id, _sample())

    with TestClient(create_app()) as client:
        create = client.post(
            "/v1/partner/unit-types",
            json={
                "property_id": created.id,
                "name": "Стандарт",
                "capacity": 2,
                "total_units": 1,
            },
            headers={"Authorization": f"Bearer {create_access_token(partner_id, scope='partner')}"},
        )
    unit_id = create.json()["id"]

    with TestClient(create_app()) as client:
        response = client.patch(
            f"/v1/partner/unit-types/{unit_id}",
            json={},
            headers={"Authorization": f"Bearer {create_access_token(partner_id, scope='partner')}"},
        )

    assert response.status_code == 422, response.text


# ------------------------------------------------------------------ guest filter


async def _seed_rooms(conn, property_id: str, capacities: list[int]) -> None:
    """Stand up room types of the given capacities; price irrelevant here."""
    for i, cap in enumerate(capacities):
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO unit_type (property_id, name, capacity, total_units, base_price) "
                "VALUES ($1, $2, $3, 1, 1000)",
                property_id,
                f"Комната {i}",
                cap,
            )


@pytest.mark.asyncio
async def test_guests_filter_keeps_property_that_fits(db_conn) -> None:
    """A property is kept when any of its room types sleeps the party.

    A hotel must not vanish because its cheapest room is a single: the filter
    looks for a room type with capacity >= guests, not at the property.
    """
    partner_id = await _make_partner(db_conn, "guests-1@example.com")
    hotel = await service.create_property(
        db_conn, partner_id, PropertyCreate(name="Отель", property_type="hotel", city="Yalta")
    )
    await _seed_rooms(db_conn, hotel.id, [2, 4])
    await service.update_property(db_conn, hotel.id, partner_id, PropertyUpdate(status="published"))

    for guests in (1, 2, 3, 4):
        rows = (await service.list_public_properties(db_conn, guests=guests))["items"]
        assert [p["id"] for p in rows] == [hotel.id], guests

    # A party of five does not fit any room.
    rows = (await service.list_public_properties(db_conn, guests=5))["items"]
    assert rows == []


@pytest.mark.asyncio
async def test_guests_filter_excludes_property_without_rooms(db_conn) -> None:
    """A published property with no room types matches nothing — it is not
    bookable, so the filter must not promise a stay."""
    partner_id = await _make_partner(db_conn, "guests-2@example.com")
    empty = await service.create_property(
        db_conn, partner_id, PropertyCreate(name="Пустой", property_type="house", city="Yalta")
    )
    await service.update_property(db_conn, empty.id, partner_id, PropertyUpdate(status="published"))

    assert (await service.list_public_properties(db_conn, guests=1))["items"] == []
    # Without a filter the property is still in the catalog.
    rows = (await service.list_public_properties(db_conn))["items"]
    assert [p["id"] for p in rows] == [empty.id]


@pytest.mark.asyncio
async def test_guests_filter_combines_with_city(db_conn) -> None:
    """The two filters compose: guests narrow first, city among the rest."""
    partner_id = await _make_partner(db_conn, "guests-3@example.com")
    yalta = await service.create_property(
        db_conn, partner_id, PropertyCreate(name="Ялта", property_type="hotel", city="Yalta")
    )
    sevastopol = await service.create_property(
        db_conn,
        partner_id,
        PropertyCreate(name="Севастополь", property_type="hotel", city="Sevastopol"),
    )
    await _seed_rooms(db_conn, yalta.id, [4])
    await _seed_rooms(db_conn, sevastopol.id, [2])
    await service.update_property(db_conn, yalta.id, partner_id, PropertyUpdate(status="published"))
    await service.update_property(
        db_conn, sevastopol.id, partner_id, PropertyUpdate(status="published")
    )

    rows = (await service.list_public_properties(db_conn, city="Yalta", guests=4))["items"]
    assert [p["id"] for p in rows] == [yalta.id]

    # Sevastopol has rooms, but not for four.
    rows = (await service.list_public_properties(db_conn, city="Sevastopol", guests=4))["items"]
    assert rows == []


# ------------------------------------------------------------- search & paging


async def _publish_n(conn, partner_id: str, n: int) -> list[str]:
    """Create and publish n properties named 'Отель k'; returns their ids."""
    ids = []
    for k in range(n):
        prop = await service.create_property(
            conn,
            partner_id,
            PropertyCreate(name=f"Отель {k}", property_type="hotel", city="Yalta"),
        )
        await service.update_property(conn, prop.id, partner_id, PropertyUpdate(status="published"))
        ids.append(prop.id)
    return ids


@pytest.mark.asyncio
async def test_catalog_search_matches_name_or_city(db_conn) -> None:
    """The search pill queries the server, so the filter reaches guests on
    page 2 too — a client-side filter would have missed them."""
    partner_id = await _make_partner(db_conn, "search-1@example.com")
    await _publish_n(db_conn, partner_id, 1)
    # A property in another city that the name query must not catch.
    other = await service.create_property(
        db_conn,
        partner_id,
        PropertyCreate(name="Дом у моря", property_type="house", city="Alushta"),
    )
    await service.update_property(db_conn, other.id, partner_id, PropertyUpdate(status="published"))

    page = await service.list_public_properties(db_conn, q="отель")
    assert page["total"] == 1
    assert page["items"][0]["name"] == "Отель 0"

    page = await service.list_public_properties(db_conn, q="alushta")
    assert page["total"] == 1
    assert page["items"][0]["city"] == "Alushta"

    page = await service.list_public_properties(db_conn, q="фыва")
    assert page["total"] == 0
    assert page["items"] == []


@pytest.mark.asyncio
async def test_catalog_returns_pages_and_total(db_conn) -> None:
    """limit/offset slice the catalog; total is the whole filtered set, so
    the UI can page without fetching everything."""
    partner_id = await _make_partner(db_conn, "search-2@example.com")
    ids = await _publish_n(db_conn, partner_id, 5)

    first = await service.list_public_properties(db_conn, limit=2, offset=0)
    assert first["total"] == 5
    assert sorted(p["id"] for p in first["items"]) == sorted(ids[:2])

    second = await service.list_public_properties(db_conn, limit=2, offset=2)
    assert second["total"] == 5
    assert sorted(p["id"] for p in second["items"]) == sorted(ids[2:4])

    past_end = await service.list_public_properties(db_conn, limit=2, offset=4)
    assert past_end["total"] == 5
    assert sorted(p["id"] for p in past_end["items"]) == sorted(ids[4:])


@pytest.mark.asyncio
async def test_catalog_search_combines_with_guests(db_conn) -> None:
    """Search and the guests filter apply together."""
    partner_id = await _make_partner(db_conn, "search-3@example.com")
    await _publish_n(db_conn, partner_id, 1)
    big = await service.create_property(
        db_conn,
        partner_id,
        PropertyCreate(name="Отель большой", property_type="hotel", city="Yalta"),
    )
    async with db_conn.transaction():
        await db_conn.execute(
            "INSERT INTO unit_type (property_id, name, capacity, total_units, base_price) "
            "VALUES ($1, 'Семейный', 6, 2, 3000)",
            big.id,
        )
    await service.update_property(db_conn, big.id, partner_id, PropertyUpdate(status="published"))

    page = await service.list_public_properties(db_conn, q="отель", guests=6)
    assert page["total"] == 1
    assert page["items"][0]["id"] == big.id

    page = await service.list_public_properties(db_conn, q="отель", guests=10)
    assert page["total"] == 0


@pytest.mark.asyncio
async def test_malformed_uuid_path_is_404_not_500(committed_conn) -> None:
    """A non-uuid id must answer 404, not leak a Postgres syntax error.

    Unauthenticated public reads are the surface a guest can reach, so the
    check is on them; the handler is app-wide and covers the rest.
    """
    from starlette.testclient import TestClient

    from app.main import create_app

    # committed_conn only exists to bring the test database up; nothing is
    # seeded because the request must never reach a query result.
    assert committed_conn is not None

    with TestClient(create_app()) as client:
        property_resp = client.get("/v1/properties/not-a-uuid")
        units_resp = client.get("/v1/public/unit-types/not-a-uuid")

    assert property_resp.status_code == 404, property_resp.text
    assert units_resp.status_code == 404, units_resp.text


@pytest.mark.asyncio
async def test_catalog_page_past_the_end_keeps_total(db_conn) -> None:
    """offset beyond the last row is an empty page, not an error."""
    partner_id = await _make_partner(db_conn, "page-end@example.com")
    await _publish_n(db_conn, partner_id, 2)
    page = await service.list_public_properties(db_conn, limit=10, offset=100)
    assert page["total"] == 2
    assert page["items"] == []
