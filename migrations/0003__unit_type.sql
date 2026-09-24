-- 0003__unit_type.sql
-- Unit type ("тип номера"). For apartments total_units=1; for hotels N physical rooms
-- of one type share one inventory row set.

CREATE TABLE IF NOT EXISTS unit_type (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id     uuid        NOT NULL REFERENCES property(id) ON DELETE CASCADE,
    name            text        NOT NULL,
    capacity        int         NOT NULL CHECK (capacity > 0),
    total_units     int         NOT NULL DEFAULT 1 CHECK (total_units > 0),
    -- Hard rule: overbooking = 0 by default. Invariant hold+sold <= total_units
    -- is enforced in the booking transaction (Slice 3).
    overbooking     int         NOT NULL DEFAULT 0 CHECK (overbooking >= 0),
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_unit_type_property ON unit_type (property_id);

COMMENT ON TABLE unit_type IS 'Тип номера/размещения';
