"""Retention for the webhook delivery ledger.

webhook_delivery grows one row per event per subscription, reconciliation reads
it, so it cannot be dropped wholesale — it ages out on purpose:

* the table is RANGE-partitioned by delivered_at, one partition per month;
* successes older than `webhook_delivery_success_days` are deleted — they are
  only the proof of a delivery, the booking itself is the source of truth;
* failures live `webhook_delivery_failed_days` longer — a failed delivery is
  what a reconciliation question is about;
* a partition whose youngest row is older than the failure window is dropped
  once it is empty, so old months do not linger.

Everything here runs off the request path, on a schedule, in `retention_loop`.

DDL in this module interpolates dates rather than binding parameters: PostgreSQL
does not accept parameters in CREATE TABLE. The values are generated here, not
supplied by a caller.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import re

import asyncpg

from app.config.settings import settings
from app.db.pool import get_pool
from app.utils.logger import get_logger

log = get_logger(__name__)

# The partitions this job owns. Anything else attached to the parent (the
# DEFAULT partition) is left alone: the sweep never drops a partition it did
# not create.
_PARTITION_RE = re.compile(r"^webhook_delivery_(\d{4})(\d{2})$")


def _month_start(date: dt.date) -> dt.date:
    return date.replace(day=1)


def _add_months(month_start: dt.date, months: int) -> dt.date:
    """Month arithmetic without dateutil: 32 days always clears a month."""
    return _month_start(month_start + dt.timedelta(days=32 * months))


def _partition_name(month_start: dt.date) -> str:
    return f"webhook_delivery_{month_start:%Y%m}"


async def ensure_partitions(conn: asyncpg.Connection, ahead_months: int) -> list[str]:
    """Create this month's partition plus `ahead_months` of headroom.

    Idempotent: the sweep calls this on every run, and a month that already
    exists is a no-op. A fresh partition is useless to the parent table without
    its unique index on (event_id, subscription_id), so both are created.
    """
    created: list[str] = []
    month = _month_start(dt.date.today())
    for i in range(ahead_months + 1):
        start = _add_months(month, i)
        end = _add_months(start, 1)
        name = _partition_name(start)
        await conn.execute(
            f"CREATE TABLE IF NOT EXISTS {name} PARTITION OF webhook_delivery "
            f"FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}')"
        )
        await conn.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {name}_event_sub_uniq "
            f"ON {name} (event_id, subscription_id)"
        )
        created.append(name)
    return created


async def prune_deliveries(
    conn: asyncpg.Connection, *, success_days: int, failed_days: int
) -> dict[str, int]:
    """Age out delivered rows, successes first.

    Reconciliation survives a thinned ledger: a booking whose proof is gone
    reports `partial` rather than `delivered`, which is exactly how a missing
    delivery is surfaced anyway. Deleting by status+age keeps the delete on one
    partition at a time and keeps the failure window longer than the success
    one, so a partner's "we never got it" is still answerable.
    """
    pruned: dict[str, int] = {}
    for status, days in (("success", success_days), ("failed", failed_days)):
        result = await conn.execute(
            """
            DELETE FROM webhook_delivery
            WHERE status = $1 AND delivered_at < now() - ($2 || ' days')::interval
            """,
            status,
            str(days),
        )
        count = int(result.split()[-1]) if result.startswith("DELETE") else 0
        pruned[status] = count
        if count:
            log.info("delivery-retention-pruned", status=status, days=days, count=count)
    return pruned


async def drop_empty_old_partitions(conn: asyncpg.Connection, *, failed_days: int) -> list[str]:
    """Drop partitions whose every row is older than the retention window.

    Empty only. A partition still holding failed rows is evidence of a problem
    and stays until the prunes delete them and a later sweep reconsiders it.
    """
    cutoff = dt.date.today() - dt.timedelta(days=failed_days)
    rows = await conn.fetch(
        """
        SELECT c.relname AS name
        FROM pg_inherits i
        JOIN pg_class c ON c.oid = i.inhrelid
        JOIN pg_class p ON p.oid = i.inhparent
        WHERE p.relname = 'webhook_delivery'
        """
    )
    dropped: list[str] = []
    for row in rows:
        name = row["name"]
        match = _PARTITION_RE.match(name)
        if match is None:
            continue
        # A partition's last day, inclusive upper bound excluded: a row at
        # exactly that instant belongs to the next partition.
        ends_at = _add_months(dt.date(int(match[1]), int(match[2]), 1), 1)
        if ends_at >= cutoff:
            continue
        count = await conn.fetchval(f'SELECT count(*) FROM "{name}"')
        if count:
            continue
        await conn.execute(f'DROP TABLE "{name}"')
        dropped.append(name)
        log.info("delivery-partition-dropped", partition=name)
    return dropped


async def run_retention(
    conn: asyncpg.Connection,
    *,
    success_days: int,
    failed_days: int,
    ahead_months: int,
) -> dict:
    """One sweep: top up future partitions, then age out old data."""
    partitions = await ensure_partitions(conn, ahead_months)
    pruned = await prune_deliveries(conn, success_days=success_days, failed_days=failed_days)
    dropped = await drop_empty_old_partitions(conn, failed_days=failed_days)
    return {
        "partitions": partitions,
        "pruned": pruned,
        "dropped": dropped,
    }


async def retention_loop() -> None:
    """Forever: keep the ledger bounded. One bad sweep never kills the next."""
    log.info(
        "retention-started",
        interval_sec=settings.retention_interval_sec,
        success_days=settings.webhook_delivery_success_days,
        failed_days=settings.webhook_delivery_failed_days,
    )
    while True:
        try:
            pool = get_pool()
            conn = await pool.acquire()
            try:
                await run_retention(
                    conn,
                    success_days=settings.webhook_delivery_success_days,
                    failed_days=settings.webhook_delivery_failed_days,
                    ahead_months=settings.webhook_delivery_partition_ahead_months,
                )
            finally:
                await pool.release(conn)
        except Exception as exc:
            log.error("retention-failed", error=str(exc))
        await asyncio.sleep(settings.retention_interval_sec)
