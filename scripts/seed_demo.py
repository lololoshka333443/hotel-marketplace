#!/usr/bin/env python3
"""Seed the demo content: two Koktebel hotels with real photos.

Goes through the database directly (a partner doing the same via the cabinet
ends up with the same rows). Idempotent — safe to re-run.

    uv run python scripts/seed_demo.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db.pool import close_pool, init_pool  # noqa: E402
from app.utils.logger import get_logger  # noqa: E402

log = get_logger(__name__)

PARTNER_EMAIL = "demo@example.com"
PARTNER_PASSWORD = "demo-password"

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin-password"

# Room photos (optimized WebP). Used as examples of what a partner uploads.
PHOTOS = {
    1: ["/rooms/1/IMG_0062.webp", "/rooms/1/IMG_0064.webp", "/rooms/1/IMG_0077.webp"],
    2: ["/rooms/2/IMG_0117.webp", "/rooms/2/IMG_0129.webp", "/rooms/2/IMG_0136.webp"],
    3: ["/rooms/3/photo_5298498534154293983_y.webp", "/rooms/3/photo_5298498534154293968_y.webp"],
    4: ["/rooms/4/IMG_1859.webp", "/rooms/4/IMG_2940.webp"],
    5: ["/rooms/5/IMG_0023.webp", "/rooms/5/IMG_0047.webp"],
    6: ["/rooms/6/IMG_E7590.webp", "/rooms/6/IMG_5242.webp"],
}

PROPERTIES = [
    {
        "name": "Выше неба",
        "rooms": [
            (1, "Семейный номер с видом на горы и террасой", 4, 1),
            (2, "Семейный номер с видом на горы и террасой", 4, 1),
        ],
    },
    {
        "name": "Седьмое небо",
        "rooms": [
            (3, "Номер с видом на море и горы", 4, 1),
            (4, "Номер с террасой и видом на горы", 4, 1),
            (5, "Номер с видом на море, горы и Коктебель", 4, 1),
            (6, "Номер с балконом и видом на горы", 4, 1),
        ],
    },
]


async def main() -> int:
    pool = await init_pool()
    try:
        async with pool.acquire() as conn:
            partner_id = await conn.fetchval(
                """
                INSERT INTO partner (email, password_hash, name)
                VALUES ($1, $2, 'Демо-партнёр')
                ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name
                RETURNING id::text
                """,
                "demo@example.com",
                # Same placeholder hash as auth/service.py - demo only.
                __import__("hashlib").sha256(b"demo-password").hexdigest(),
            )

            # Reassign any objects from a superseded demo partner so a re-seed
            # never leaves orphan properties the current token cannot see.
            await conn.execute(
                """
                UPDATE property SET partner_id = $1
                 WHERE partner_id IN (
                     SELECT id FROM partner WHERE email <> 'demo@example.com'
                 )
                """,
                partner_id,
            )

            for property_def in PROPERTIES:
                room_numbers = [r[0] for r in property_def["rooms"]]
                photos_json = json.dumps(
                    [p for n in room_numbers for p in PHOTOS.get(n, [])]
                )
                address = json.dumps({"settlement": "Коктебель", "region": "Крым"})

                property_id = await conn.fetchval(
                    """
                    UPDATE property
                       SET photos = $3, status = 'published'
                     WHERE partner_id = $1 AND name = $2
                    RETURNING id::text
                    """,
                    partner_id,
                    property_def["name"],
                    photos_json,
                )
                if property_id is None:
                    property_id = await conn.fetchval(
                        """
                        INSERT INTO property (partner_id, name, property_type, city, timezone,
                                              status, address, photos)
                        VALUES ($1, $2, 'hotel', 'Коктебель', 'Europe/Simferopol',
                                'published', $3, $4)
                        RETURNING id::text
                        """,
                        partner_id,
                        property_def["name"],
                        address,
                        photos_json,
                    )

                for room_no, room_name, capacity, total_units in property_def["rooms"]:
                    existing = await conn.fetchval(
                        "SELECT id::text FROM unit_type WHERE property_id = $1 AND name = $2",
                        property_id,
                        f"Номер {room_no} · {room_name}",
                    )
                    if existing:
                        continue
                    unit_type_id = await conn.fetchval(
                        """
                        INSERT INTO unit_type (property_id, name, capacity, total_units)
                        VALUES ($1, $2, $3, $4)
                        RETURNING id::text
                        """,
                        property_id,
                        f"Номер {room_no} · {room_name}",
                        capacity,
                        total_units,
                    )
                    if unit_type_id:
                        await conn.execute(
                            """
                            INSERT INTO inventory_day (unit_type_id, date, available)
                            SELECT $1, d::date, $2
                            FROM generate_series(
                                CURRENT_DATE, CURRENT_DATE + interval '365 days', '1 day'
                            ) AS d
                            WHERE NOT EXISTS (
                                SELECT 1 FROM inventory_day i
                                WHERE i.unit_type_id = $1 AND i.date = d::date
                            )
                            """,
                            unit_type_id,
                            total_units,
                        )
                log.info("property-seeded", name=property_def["name"], id=property_id)

            # Staff account for the admin panel (reports + moderation).
            await conn.execute(
                """
                INSERT INTO admin (email, password_hash)
                VALUES ($1, $2)
                ON CONFLICT (email) DO NOTHING
                """,
                ADMIN_EMAIL,
                __import__("hashlib").sha256(ADMIN_PASSWORD.encode()).hexdigest(),
            )

            print(
                f"seeded: partner {PARTNER_EMAIL} / {len(PROPERTIES)} properties, "
                f"admin {ADMIN_EMAIL}"
            )
    finally:
        await close_pool()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
