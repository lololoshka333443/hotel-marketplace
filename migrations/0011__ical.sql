-- 0011__ical.sql
-- iCal export feeds. One feed per unit type; the token in the URL is the secret
-- (no login for calendar clients). Channels poll GET /v1/ical/{token}.ics.

CREATE TABLE IF NOT EXISTS ical_feed (
    id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    unit_type_id uuid        NOT NULL REFERENCES unit_type(id) ON DELETE CASCADE,
    token        text        NOT NULL UNIQUE,
    enabled      boolean     NOT NULL DEFAULT true,
    created_at   timestamptz NOT NULL DEFAULT now(),
    -- one feed per unit type: rotate the token instead of adding a second feed
    UNIQUE (unit_type_id)
);

COMMENT ON TABLE ical_feed IS 'iCal-фид экспорта доступности по типу номера';
