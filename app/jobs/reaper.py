"""Background jobs.

The hold reaper cancels bookings whose TTL expired, returning their inventory
to the pool. Runs every minute; each sweep is bounded.
"""

from __future__ import annotations

import asyncio

from app.db.pool import get_pool
from app.modules.booking import service
from app.utils.logger import get_logger

log = get_logger(__name__)

REAPER_INTERVAL_SEC = 60
_STOP = asyncio.Event()


async def reaper_loop() -> None:
    """Cancel expired holds on a fixed cadence until stopped."""
    log.info("reaper-started", interval_sec=REAPER_INTERVAL_SEC)
    while not _STOP.is_set():
        try:
            conn = await get_pool().acquire()
            try:
                await service.expire_holds(conn)
            finally:
                await get_pool().release(conn)
        except Exception as exc:
            log.error("reaper-failed", error=str(exc))
        await asyncio.sleep(REAPER_INTERVAL_SEC)


def stop_reaper() -> None:
    _STOP.set()
