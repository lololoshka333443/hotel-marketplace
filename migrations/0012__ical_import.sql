-- 0012__ical_import.sql
-- External calendar subscriptions imported INTO our inventory.
--
-- Semantics: imported blocks become inventory_day.closed = true (stop sell),
-- tagged with their origin. New bookings on those dates are refused, but
-- existing paid bookings are never touched - our DB is the source of truth,
-- an external feed does not cancel real money.
--
-- closed_source separates partner-made closures from imported ones so the
-- importer can safely unblock only what it blocked itself.

ALTER TABLE inventory_day
    ADD COLUMN IF NOT EXISTS closed_source text NOT NULL DEFAULT 'manual';

CREATE TABLE IF NOT EXISTS ical_subscription (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    unit_type_id    uuid        NOT NULL REFERENCES unit_type(id) ON DELETE CASCADE,
    url             text        NOT NULL,
    enabled         boolean     NOT NULL DEFAULT true,
    last_synced_at  timestamptz,
    last_status     text        NOT NULL DEFAULT 'pending',  -- ok | error
    last_error      text,
    last_blocked    int         NOT NULL DEFAULT 0,
    created_at      timestamptz NOT NULL DEFAULT now(),
    -- one import per unit type; replace the URL instead of adding a second
    UNIQUE (unit_type_id)
);

CREATE INDEX IF NOT EXISTS idx_ical_subscription_sync
    ON ical_subscription (enabled, last_synced_at)
    WHERE enabled;

COMMENT ON TABLE ical_subscription IS 'Внешний iCal-календарь, импортируемый в тип номера';
