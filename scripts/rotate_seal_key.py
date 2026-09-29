#!/usr/bin/env python3
"""Re-seal webhook subscription secrets onto the current seal key.

Rotation without downtime: put the outgoing key in WEBHOOK_SEAL_KEY_PREVIOUS
and the new one in WEBHOOK_SEAL_KEY, then run this. unseal() falls back to the
previous key, so deliveries keep going while the rows are walked; this script
writes each secret back under the new key only. When it reports nothing left,
drop WEBHOOK_SEAL_KEY_PREVIOUS.

Idempotent — rows already on the current key are left untouched.

    uv run python scripts/rotate_seal_key.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import asyncpg  # noqa: E402

from app.config.settings import settings  # noqa: E402
from app.db.pool import close_pool, init_pool  # noqa: E402
from app.utils.logger import get_logger  # noqa: E402
from app.utils.secrets import (  # noqa: E402
    seal,
    unseal,
    unseals_with_current_key,
)

log = get_logger(__name__)

_LEGACY_PREFIX = "LEGACY:"

# A Fernet token is urlsafe-base64: letters, digits, -, _, = padding and the
# dots Fernet uses as separators. A plaintext secret never looks like that.
_TOKEN_CHARS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.="
)


def _looks_like_a_token(value: str) -> bool:
    return len(value) > 40 and all(c in _TOKEN_CHARS for c in value)


async def rotate(conn: asyncpg.Connection) -> dict[str, int]:
    stats = {"resealed": 0, "already_current": 0, "unsealable": 0, "legacy": 0}
    rows = await conn.fetch("SELECT id::text, secret_sealed FROM webhook_subscription")
    for row in rows:
        stored = row["secret_sealed"]
        if stored is None:
            continue
        if not _looks_like_a_token(stored):
            # Pre-migration plaintext, still unsealed. The delivery path seals
            # it on first use; report it so it is not mistaken for a rotated
            # row.
            stats["legacy"] += 1
            continue
        if unseals_with_current_key(stored):
            stats["already_current"] += 1
            continue
        try:
            plaintext = unseal(stored)
        except RuntimeError:
            stats["unsealable"] += 1
            log.warning("seal-key-rotation-unsealable", subscription_id=row["id"])
            continue
        await conn.execute(
            "UPDATE webhook_subscription SET secret_sealed = $2 WHERE id = $1",
            row["id"],
            seal(plaintext),
        )
        stats["resealed"] += 1
    return stats


async def main() -> int:
    if not settings.webhook_seal_key:
        print("WEBHOOK_SEAL_KEY is not configured. Nothing to rotate onto.")
        return 1
    if not settings.webhook_seal_key_previous:
        print(
            "WEBHOOK_SEAL_KEY_PREVIOUS is not set — every row should already be\n"
            "on the current key. Run this with the outgoing key in PREVIOUS."
        )

    pool = await init_pool()
    try:
        conn = await pool.acquire()
        try:
            stats = await rotate(conn)
        finally:
            await pool.release(conn)
    finally:
        await close_pool()

    print(
        f"re-sealed: {stats['resealed']}  "
        f"already on the current key: {stats['already_current']}  "
        f"unsealable: {stats['unsealable']}  "
        f"unsealed (LEGACY) rows: {stats['legacy']}"
    )
    if stats["unsealable"]:
        print(
            "\nUnsealable rows were sealed with a key that is neither the current\n"
            "nor the previous one. Their secrets are gone — those subscriptions\n"
            "are already skipped at delivery; re-create them if they matter."
        )
        return 2
    if stats["legacy"]:
        print("\nUnsealed LEGACY rows are re-sealed by the delivery path on first use.")
    print(
        "\nEverything readable is on the current key. "
        "Drop WEBHOOK_SEAL_KEY_PREVIOUS now."
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
