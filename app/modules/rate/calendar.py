"""Partner calendar (шахматка).

One row per unit_type, one column per date. Each cell combines inventory
state (free/held/sold/closed) with the effective price. This is the single
most important screen of the partner cabinet.
"""

from __future__ import annotations

import datetime as dt

import asyncpg

from app.utils.logger import get_logger

log = get_logger(__name__)


async def get_calendar(
    conn: asyncpg.Connection,
    partner_id: str,
    date_from: dt.date,
    date_to: dt.date,
    property_id: str | None = None,
) -> dict:
    """Grid of availability + price for every unit type the partner owns.

    Half-open interval [date_from, date_to).
    """
    if date_to <= date_from:
        raise ValueError("date_to must be after date_from")
    if (date_to - date_from).days > 92:
        raise ValueError("calendar range cannot exceed 92 days")

    args: list = [partner_id, date_from, date_to]
    prop_filter = ""
    if property_id is not None:
        args.append(property_id)
        prop_filter = "AND p.id = $4"

    rows = await conn.fetch(
        f"""
        SELECT ut.id::text            AS unit_type_id,
               ut.name                AS unit_type_name,
               p.id::text             AS property_id,
               p.name                 AS property_name,
               ut.total_units,
               ut.base_price::float8,
               COALESCE(rp.id::text, '') AS rate_plan_id,
               d.date,
               i.available,
               i.hold,
               i.sold,
               i.closed,
               COALESCE(pd.price::float8, ut.base_price::float8) AS price,
               COALESCE(pd.min_stay, 1) AS min_stay,
               COALESCE(pd.stop_sell, false) AS stop_sell
        FROM property p
        JOIN unit_type ut  ON ut.property_id = p.id
        LEFT JOIN rate_plan rp
               ON rp.unit_type_id = ut.id AND rp.active
        LEFT JOIN LATERAL (
            SELECT generate_series($2::date, ($3::date - interval '1 day')::date, '1 day')::date AS date
        ) d ON true
        LEFT JOIN inventory_day i
               ON i.unit_type_id = ut.id AND i.date = d.date
        LEFT JOIN price_day pd
               ON pd.rate_plan_id = rp.id AND pd.date = d.date
        WHERE p.partner_id = $1 {prop_filter}
        ORDER BY p.name, ut.name, d.date
        """,
        *args,
    )

    # Group rows into {unit_type: {date: cell}}
    units: dict[str, dict] = {}
    for r in rows:
        ut_id = r["unit_type_id"]
        if ut_id not in units:
            units[ut_id] = {
                "unit_type_id": ut_id,
                "unit_type_name": r["unit_type_name"],
                "property_id": r["property_id"],
                "property_name": r["property_name"],
                "total_units": r["total_units"],
                "rate_plan_id": r["rate_plan_id"] or None,
                "days": [],
            }
        available = r["available"] or 0
        hold = r["hold"] or 0
        sold = r["sold"] or 0
        closed = bool(r["closed"]) or bool(r["stop_sell"])
        units[ut_id]["days"].append(
            {
                "date": r["date"].isoformat()
                if hasattr(r["date"], "isoformat")
                else str(r["date"]),
                "available": available,
                "hold": hold,
                "sold": sold,
                "free": max(available - hold - sold, 0),
                "closed": closed,
                "price": r["price"],
                "min_stay": r["min_stay"],
            }
        )

    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "units": list(units.values()),
    }
