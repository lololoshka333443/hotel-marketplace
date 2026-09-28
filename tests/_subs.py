"""Shared test helpers for webhook subscriptions.

Subscription secrets are sealed at rest now, and a raw plaintext in the column
is not readable back — it is neither a Fernet token nor a LEGACY-marked row.
Anything that inserts a subscription directly must go through here so the
secret it stores is the sealed form, exactly as the API route would write it.
"""

from __future__ import annotations

import asyncpg

from app.utils.secrets import seal as seal_secret


async def subscribe(
    conn: asyncpg.Connection,
    partner_id: str,
    url: str,
    secret: str,
    event_types: tuple[str, ...] = ("*",),
    enabled: bool = True,
) -> str:
    """Insert a subscription with a sealed secret. Returns the subscription id."""
    return await conn.fetchval(
        """
        INSERT INTO webhook_subscription
            (partner_id, url, event_types, secret, secret_sealed, enabled)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id::text
        """,
        partner_id,
        url,
        list(event_types),
        secret,
        seal_secret(secret),
        enabled,
    )
