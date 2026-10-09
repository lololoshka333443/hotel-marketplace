-- 0023__rate_plan_commission.sql
-- Commission rate lives on the rate plan, not in a global constant.
--
-- Q13 of the product questionnaire (ARCHITECTURE.md §10) asked: flat % or per
-- season / property category. A rate plan already carries the cancellation
-- policy and the seasonal price_day rows, so it is the natural home for the
-- commission share that applies to the nights it prices.
--
-- NULL means "use the platform default" (app.config.legal), which keeps every
-- existing rate plan on 12% without a backfill. The booking still snapshots
-- commission_rate at hold time, so a later change never reprices a booking
-- that is already confirmed — reports keep reading the snapshot.

ALTER TABLE rate_plan
    ADD COLUMN IF NOT EXISTS commission_rate numeric(5,4)
        CHECK (commission_rate >= 0 AND commission_rate <= 1);

COMMENT ON COLUMN rate_plan.commission_rate IS
    'Доля комиссии платформы для ночей этого тарифа; NULL = ставка по умолчанию';
