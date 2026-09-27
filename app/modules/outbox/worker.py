"""Outbox delivery loop.

Same shape as the reaper and the iCal poller: a tolerant forever loop that
claims a batch, does the slow network work outside any transaction, and never
lets one bad iteration kill the next one.

Delivery states:
  pending      -> waiting for a slot
  delivering   -> claimed, HTTP in flight
  published    -> every subscriber answered 2xx (or there were none)
  failed       -> max_attempts reached; dead-lettered for manual retry
"""

from __future__ import annotations

import asyncio
import contextlib

import asyncpg

from app.db.pool import get_pool
from app.modules.outbox import deliver, service
from app.utils.logger import get_logger

log = get_logger(__name__)

POLL_INTERVAL_SEC = 15
BATCH = 50
# Rows sitting in 'delivering' longer than this are from a dead worker.
STALE_SEC = 300


async def outbox_loop() -> None:
    """Forever: reclaim orphans, then deliver what is due."""
    while True:
        try:
            pool = get_pool()
            conn = await pool.acquire()
            try:
                await service.reclaim_stale(conn, STALE_SEC)
                await _run_batch(conn)
            finally:
                await pool.release(conn)
        except Exception as exc:
            log.error("outbox-loop-error", error=str(exc))
        await asyncio.sleep(POLL_INTERVAL_SEC)


async def _run_batch(conn: asyncpg.Connection) -> None:
    events = await service.claim_due(conn, BATCH)
    if not events:
        return

    for event in events:
        with contextlib.suppress(Exception):
            await _deliver_one(conn, event)


async def _deliver_one(conn: asyncpg.Connection, event: dict) -> None:
    subs = await service.subscribers_for(conn, event["id"], event["event_type"])

    # Nobody is listening (or everyone already got it): the event is done.
    if not subs:
        await service.mark_published(conn, event["id"])
        return

    errors: list[str] = []
    for sub in subs:
        ok, status_code, error = await deliver.deliver(
            sub["url"], sub["secret"], event
        )
        await service.record_delivery(
            conn, event["id"], sub["id"], ok, status_code, error
        )
        if not ok:
            errors.append(f"{sub['url']}: {error}")

    if not errors:
        await service.mark_published(conn, event["id"])
        log.info("outbox-published", event_id=event["id"], subs=len(subs))
    else:
        await service.mark_retry(
            conn, event["id"], event["attempts"] + 1, "; ".join(errors)
        )
        log.warning(
            "outbox-delivery-failed",
            event_id=event["id"],
            attempts=event["attempts"] + 1,
            error="; ".join(errors),
        )
