-- 0007__rate_plan.sql
-- Rate plans + per-night prices/restrictions.

CREATE TABLE IF NOT EXISTS rate_plan (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    unit_type_id        uuid        NOT NULL REFERENCES unit_type(id) ON DELETE CASCADE,
    name                text        NOT NULL,
    cancellation_policy text        NOT NULL DEFAULT 'flexible'
                        CHECK (cancellation_policy IN ('flexible','moderate','strict')),
    active              boolean     NOT NULL DEFAULT true,
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rate_plan_unit ON rate_plan (unit_type_id);

CREATE TABLE IF NOT EXISTS price_day (
    rate_plan_id    uuid          NOT NULL REFERENCES rate_plan(id) ON DELETE CASCADE,
    date            date          NOT NULL,
    price           numeric(12,2) NOT NULL CHECK (price >= 0),
    min_stay        int           NOT NULL DEFAULT 1 CHECK (min_stay >= 1),
    max_stay        int,
    cta             boolean       NOT NULL DEFAULT true,   -- check-in allowed
    ctd             boolean       NOT NULL DEFAULT true,   -- check-out allowed
    stop_sell       boolean       NOT NULL DEFAULT false,
    PRIMARY KEY (rate_plan_id, date)
);
