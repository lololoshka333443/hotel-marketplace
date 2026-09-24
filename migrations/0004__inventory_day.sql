-- 0004__inventory_day.sql
-- Allotment per (unit_type, date). One row per night.
-- The booking core (Slice 3) locks these rows with FOR UPDATE.

CREATE TABLE IF NOT EXISTS inventory_day (
    unit_type_id    uuid        NOT NULL REFERENCES unit_type(id) ON DELETE CASCADE,
    date            date        NOT NULL,
    available       int         NOT NULL DEFAULT 0 CHECK (available >= 0),
    hold            int         NOT NULL DEFAULT 0 CHECK (hold >= 0),
    sold            int         NOT NULL DEFAULT 0 CHECK (sold >= 0),
    closed          boolean     NOT NULL DEFAULT false,
    PRIMARY KEY (unit_type_id, date)
);

-- Range queries for the availability endpoint and calendar grid.
CREATE INDEX IF NOT EXISTS idx_inventory_date ON inventory_day (date);

COMMENT ON TABLE inventory_day IS 'Allotment по дням: available = total_units - hold - sold';
