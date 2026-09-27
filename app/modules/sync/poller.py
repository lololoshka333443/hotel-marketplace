"""Background iCal importer.

Polls subscribed calendars on an interval (settings.ical_sync_interval_sec) and
pulls their blocked dates into inventory. The reaper in app/jobs/reaper.py is
the model: same loop shape, same tolerance for a failing iteration.
"""

from __future__ import annotations

import asyncio
import contextlib

import asyncpg

from app.db.pool import get_pool
from app.modules.sync import ical_import
from app.utils.logger import get_logger

log = get_logger(__name__)

POLL_INTERVAL_SEC = 60
BATCH = 25


async def import_loop() -> None:
    """Forever: every POLL_INTERVAL_SEC, sync subscriptions that are due."""
    while True:
        try:
            pool = get_pool()
            conn = await pool.acquire()
            try:
                await _run_batch(conn)
            finally:
                await pool.release(conn)
        except Exception as exc:
            log.error("ical-import-loop-error", error=str(exc))
        await asyncio.sleep(POLL_INTERVAL_SEC)


async def _run_batch(conn: asyncpg.Connection) -> None:
    # list_due claims rows atomically; no lock is held across the network fetch.
    due = await ical_import.list_due(conn, BATCH)

    if not due:
        return

    for subscription_id in due:
        with contextlib.suppress(Exception):
            await ical_import.sync_subscription(conn, subscription_id)
