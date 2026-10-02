"""Property service.

All functions take an `asyncpg.Connection` so tests can pass a rolled-back
transaction.

Access rule: a partner can only touch their own properties. This is enforced
in the routes by passing the partner_id from the JWT.
"""

from __future__ import annotations

import json
import secrets

import asyncpg

from app.modules.property.schemas import PropertyCreate, PropertyOut, PropertyUpdate
from app.utils.logger import get_logger

log = get_logger(__name__)


def _jsonb(v) -> dict:
    """asyncpg returns jsonb columns as str unless a codec is registered."""
    import json

    if isinstance(v, str):
        return json.loads(v)
    return v or {}


def _make_slug(name: str) -> str:
    """Transliteration-free slug: name → latin-safe short token.

    Cyrillic is kept as-is but stripped of spaces; a random suffix guarantees
    uniqueness. Slice 1 keeps this intentionally simple.
    """
    base = "".join(c if (c.isalnum() or c == "-") else "-" for c in name.lower())
    base = base.strip("-")[:40] or "property"
    return f"{base}-{secrets.token_hex(3)}"


async def create_property(
    conn: asyncpg.Connection, partner_id: str, data: PropertyCreate
) -> PropertyOut:
    row = await conn.fetchrow(
        """
        INSERT INTO property
            (partner_id, name, slug, property_type, city, timezone,
             checkin_time, checkout_time, currency, lat, lng, address, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, 'draft')
        RETURNING
            id::text, partner_id::text, name, slug, property_type, city, timezone,
            checkin_time, checkout_time, currency, status,
            lat::float8, lng::float8, address::jsonb, created_at
        """,
        partner_id,
        data.name,
        _make_slug(data.name),
        data.property_type,
        data.city,
        data.timezone,
        data.checkin_time,
        data.checkout_time,
        data.currency,
        data.lat,
        data.lng,
        json.dumps(data.address),
    )
    assert row is not None
    log.info("property-created", partner_id=partner_id, name=data.name)
    return PropertyOut(
        id=row["id"],
        partner_id=row["partner_id"],
        name=row["name"],
        slug=row["slug"],
        property_type=row["property_type"],
        city=row["city"],
        timezone=row["timezone"],
        checkin_time=row["checkin_time"],
        checkout_time=row["checkout_time"],
        currency=row["currency"],
        status=row["status"],
        lat=row["lat"],
        lng=row["lng"],
        address=_jsonb(row["address"]),
        created_at=row["created_at"],
    )


async def get_partner_properties(conn: asyncpg.Connection, partner_id: str) -> list[PropertyOut]:
    rows = await conn.fetch(
        """
        SELECT id::text, partner_id::text, name, slug, property_type, city, timezone,
               checkin_time, checkout_time, currency, status,
               lat::float8, lng::float8, address::jsonb, created_at
        FROM property
        WHERE partner_id = $1
        ORDER BY created_at DESC
        """,
        partner_id,
    )
    return [_row_to_out(r) for r in rows]


async def get_property_for_partner(
    conn: asyncpg.Connection, property_id: str, partner_id: str
) -> PropertyOut | None:
    """Fetch a property, but ONLY if it belongs to this partner."""
    row = await conn.fetchrow(
        """
        SELECT id::text, partner_id::text, name, slug, property_type, city, timezone,
               checkin_time, checkout_time, currency, status,
               lat::float8, lng::float8, address::jsonb, created_at
        FROM property
        WHERE id = $1 AND partner_id = $2
        """,
        property_id,
        partner_id,
    )
    return _row_to_out(row) if row else None


async def get_public_property(conn: asyncpg.Connection, property_id: str) -> dict | None:
    """Public catalog read: published only, no partner-internal fields."""
    row = await conn.fetchrow(
        """
        SELECT p.id::text, p.name, p.slug, p.property_type, p.city, p.timezone,
               p.checkin_time, p.checkout_time, p.currency,
               p.lat::float8, p.lng::float8, p.address::jsonb, p.photos::jsonb,
               (SELECT min(ut.base_price)::float8
                  FROM unit_type ut
                 WHERE ut.property_id = p.id) AS min_price
        FROM property p
        WHERE p.id = $1 AND p.status = 'published'
        """,
        property_id,
    )
    if row is None:
        return None
    return dict(row, address=_jsonb(row["address"]), photos=_jsonb(row["photos"]))


async def list_public_properties(
    conn: asyncpg.Connection,
    city: str | None = None,
    guests: int | None = None,
    q: str | None = None,
    limit: int = 24,
    offset: int = 0,
) -> dict:
    """Published catalog with the filters a guest actually narrows on.

    `guests` keeps a property that has *any* room type sleeping that many — a
    hotel is not excluded because its cheapest room is a single. Properties
    without room types never match, which is right: they are not bookable yet.
    `q` matches the name or the city, the two things the search pill offered.
    Returns a page plus the total, so the UI can page without fetching all.
    """
    args: list = []
    where = "p.status = 'published'"
    if city:
        args.append(city)
        where += f" AND p.city = ${len(args)}"
    if guests:
        args.append(guests)
        where += (
            f" AND EXISTS (SELECT 1 FROM unit_type ut"
            f" WHERE ut.property_id = p.id AND ut.capacity >= ${len(args)})"
        )
    if q:
        args.append(f"%{q}%")
        where += f" AND (p.name ILIKE ${len(args)} OR p.city ILIKE ${len(args)})"

    total = await conn.fetchval(
        f"SELECT count(*) FROM property p WHERE {where}",
        *args,
    )

    args.append(limit)
    args.append(offset)
    rows = await conn.fetch(
        f"""
        SELECT p.id::text, p.name, p.slug, p.property_type, p.city, p.timezone,
               p.checkin_time, p.checkout_time, p.currency,
               p.lat::float8, p.lng::float8, p.address::jsonb, p.photos::jsonb,
               (SELECT min(ut.base_price)::float8
                  FROM unit_type ut
                 WHERE ut.property_id = p.id) AS min_price
        FROM property p
        WHERE {where}
        ORDER BY p.created_at DESC
        LIMIT ${len(args) - 1} OFFSET ${len(args)}
        """,
        *args,
    )
    out = []
    for r in rows:
        row = dict(r, address=_jsonb(r["address"]), photos=_jsonb(r["photos"]))
        # No room types yet: the property is published but unbookable, and
        # min_price None is exactly that — the UI says "цена не указана".
        row["min_price"] = r["min_price"]
        out.append(row)
    return {"items": out, "total": total, "limit": limit, "offset": offset}


async def update_property(
    conn: asyncpg.Connection, property_id: str, partner_id: str, data: PropertyUpdate
) -> PropertyOut | None:
    """Partial update; returns None if the property is not owned by partner."""
    fields = data.model_dump(exclude_unset=True)
    if not fields:
        saved = await get_property_for_partner(conn, property_id, partner_id)
        return saved

    if "address" in fields:
        fields["address"] = json.dumps(fields["address"])

    cols = list(fields)
    assignments = ", ".join(f"{c} = ${i + 3}" for i, c in enumerate(cols))
    values = [property_id, partner_id, *[fields[c] for c in cols]]

    row = await conn.fetchrow(
        f"""
        UPDATE property
        SET {assignments}
        WHERE id = $1 AND partner_id = $2
        RETURNING id::text, partner_id::text, name, slug, property_type, city, timezone,
                  checkin_time, checkout_time, currency, status,
                  lat::float8, lng::float8, address::jsonb, created_at
        """,
        *values,
    )
    return _row_to_out(row) if row else None


def _row_to_out(row: asyncpg.Record) -> PropertyOut:
    return PropertyOut(
        id=row["id"],
        partner_id=row["partner_id"],
        name=row["name"],
        slug=row["slug"],
        property_type=row["property_type"],
        city=row["city"],
        timezone=row["timezone"],
        checkin_time=row["checkin_time"],
        checkout_time=row["checkout_time"],
        currency=row["currency"],
        status=row["status"],
        lat=row["lat"],
        lng=row["lng"],
        address=_jsonb(row["address"]),
        created_at=row["created_at"],
    )


async def list_public_unit_types(conn: asyncpg.Connection, property_id: str) -> list[dict]:
    """The guest's room list for one published property, cheapest price included.

    A rate plan overrides base_price when it has rows for the date; see
    rate.get_effective_price for the same fallback in the availability path.
    The price shown is the cheapest night across the next 30 days, so a guest
    browsing the catalog sees what the stay actually costs instead of reaching
    the checkout to find out.
    """
    rows = await conn.fetch(
        """
        SELECT ut.id::text, ut.property_id::text, ut.name, ut.capacity,
               ut.total_units,
               COALESCE(
                 (SELECT min(pd.price)::float8
                  FROM price_day pd
                  JOIN rate_plan rp ON rp.id = pd.rate_plan_id
                  WHERE rp.unit_type_id = ut.id AND rp.active
                    AND pd.date >= current_date
                    AND pd.date < current_date + interval '30 days'
                    AND pd.stop_sell = false),
                 ut.base_price::float8
               ) AS price
        FROM unit_type ut
        WHERE ut.property_id = $1
        ORDER BY ut.created_at
        """,
        property_id,
    )
    return [dict(r) for r in rows]
