-- 0015__webhook_delivery_retention.sql
-- The delivery ledger ages out.
--
-- webhook_delivery grows without bound (every event × every subscription) and
-- reconciliation reads it, so it cannot be dropped wholesale — it has to age
-- out on purpose. From now on the table is RANGE-partitioned by delivered_at,
-- one partition per month, and a background sweep
-- (app/modules/outbox/retention.py) prunes old rows and drops old empty
-- partitions on a schedule, never in a request.
--
-- Two PostgreSQL constraints shape this migration:
--
--  * A partitioned table cannot be the referencing end of a foreign key, so
--    the FKs to outbox_event / webhook_subscription are gone. The worker only
--    ever writes rows for an event it holds a claim on, the ledger is a leaf
--    (nothing references it), and outbox_event has no retention of its own —
--    so nothing deletes a parent and orphans a delivery.
--  * A unique constraint on a partitioned table must include the partition
--    key, which would defeat its purpose, so uniqueness of
--    (event_id, subscription_id) is enforced per partition instead. One pair
--    only ever lives in one partition: the claim is SKIP LOCKED, so a single
--    worker owns an event end to end, and service.record_delivery upserts by
--    that pair.

CREATE TABLE webhook_delivery_new (
    id              uuid        NOT NULL DEFAULT gen_random_uuid(),
    event_id        uuid        NOT NULL,
    subscription_id uuid        NOT NULL,
    status          text        NOT NULL CHECK (status IN ('success','failed')),
    status_code     int,
    error           text,
    delivered_at    timestamptz NOT NULL DEFAULT now()
) PARTITION BY RANGE (delivered_at);

INSERT INTO webhook_delivery_new (
    id, event_id, subscription_id, status, status_code, error, delivered_at
)
SELECT id, event_id, subscription_id, status, status_code, error, delivered_at
FROM webhook_delivery;

DROP TABLE webhook_delivery;
ALTER TABLE webhook_delivery_new RENAME TO webhook_delivery;

-- Catches a month the sweep has not created yet, so a delivery never fails on
-- missing DDL. Rows landing here are still covered by the sweep's DELETE.
CREATE TABLE webhook_delivery_default PARTITION OF webhook_delivery DEFAULT;

CREATE UNIQUE INDEX webhook_delivery_default_event_sub_uniq
    ON webhook_delivery_default (event_id, subscription_id);

-- First partitions: this month and a few ahead, so the table accepts inserts
-- the moment this migration lands. The sweep keeps creating them from here.
DO $$
DECLARE
    i int;
    m date := date_trunc('month', now())::date;
    n date;
BEGIN
    FOR i IN 0..3 LOOP
        n := (m + (i || ' month')::interval)::date;
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF webhook_delivery '
            'FOR VALUES FROM (%L) TO (%L)',
            'webhook_delivery_' || to_char(n, 'YYYYMM'),
            n,
            (n + interval '1 month')::date
        );
        EXECUTE format(
            'CREATE UNIQUE INDEX IF NOT EXISTS %I ON %I (event_id, subscription_id)',
            'webhook_delivery_' || to_char(n, 'YYYYMM') || '_event_sub_uniq',
            'webhook_delivery_' || to_char(n, 'YYYYMM')
        );
    END LOOP;
END $$;

COMMENT ON TABLE webhook_delivery IS
    'Лог доставки события конкретной подписке — для reconciliation. '
    'Партицирован по delivered_at помесячно; старое вычищает retention-джоба.';
