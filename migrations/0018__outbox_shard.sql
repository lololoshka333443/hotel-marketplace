-- 0018__outbox_shard.sql
-- The outbox delivers through one worker, one batch at a time. That is one
-- queue for every partner: a bulk price load of a few thousand events sits in
-- one worker's claim order, and while a booking is claimed first by priority,
-- the worker still walks the bulk rows of partner A before it gets to partner
-- B's anything. One process, one connection, one sequence of HTTP calls.
--
-- Sharding splits that one queue into outbox_shard_count logical shards by the
-- property the event is about, and spreads them across outbox_workers delivery
-- loops. Each worker claims only its own shards, so:
--
--  * delivery parallelises — N workers, N connections, N batches in flight;
--  * partners stop queuing behind each other — a property's events all land in
--    one shard, so one partner's burst never sits in another's claim order;
--  * per-property order survives — all of a property's events share a shard
--    with one worker, which still claims them by priority and due time.
--
-- This is a *logical* shard, not physical partitioning (as opposed to
-- webhook_delivery's RANGE partitions). outbox_event is a draining queue, not
-- an append-only log: partitioning it would force the primary key to include
-- the partition key — every id-based path (mark_published, mark_retry,
-- release_claim, the admin retry) would have to know the shard — and would
-- rewrite the whole table in a migration. A column and one index is the whole
-- mechanism, and the code paths that do not care about shards (reclaim,
-- reconciliation, metrics, backlog depth) keep working unchanged.
--
-- The shard value is abs(hashtext(...)) % shard_count, computed in SQL both
-- here and at emit() — one source of truth, no Python hash to keep in sync.
-- hashtext returns a *signed* int4, so without abs half the shards would be
-- negative and no worker would ever own them.
ALTER TABLE outbox_event
    ADD COLUMN IF NOT EXISTS shard smallint NOT NULL DEFAULT 0;

-- Existing rows were emitted before sharding; place them by the same
-- expression emit() uses. property_id is NULL only if resolution failed, in
-- which case aggregate_id still separates the streams.
UPDATE outbox_event
SET shard = abs(hashtext(coalesce(property_id::text, aggregate_id))) % 16;

-- claim_due now slices by shard first; the ordering columns follow it.
DROP INDEX IF EXISTS idx_outbox_due;
CREATE INDEX idx_outbox_due
    ON outbox_event (shard, priority, next_attempt_at, happened_at)
    WHERE status IN ('pending', 'delivering');

COMMENT ON COLUMN outbox_event.shard IS
    'Логический шард: abs(hashtext(property)) % 16. Воркеры доставки делят их между собой';
