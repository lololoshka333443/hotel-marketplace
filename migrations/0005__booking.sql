-- 0005__booking.sql
-- Booking + booking lines. The heart of the platform.

-- Simple per-night price for Slice 3; rate_plan/price_day arrive in Slice 5
-- and will override pricing when present.
ALTER TABLE unit_type ADD COLUMN IF NOT EXISTS base_price numeric(12,2)
    NOT NULL DEFAULT 0 CHECK (base_price >= 0);

CREATE TABLE IF NOT EXISTS booking (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    code             text        UNIQUE NOT NULL,
    idempotency_key  text        UNIQUE,
    property_id      uuid        NOT NULL REFERENCES property(id),
    unit_type_id     uuid        NOT NULL REFERENCES unit_type(id),
    guest_name       text        NOT NULL,
    guest_email      citext      NOT NULL,
    guest_phone      text        NOT NULL,
    checkin_date     date        NOT NULL,
    checkout_date    date        NOT NULL,
    status           text        NOT NULL DEFAULT 'hold'
                     CHECK (status IN ('hold','paid','confirmed','cancelled',
                                       'failed','conflict','no_show','refunded')),
    origin           text        NOT NULL DEFAULT 'web' CHECK (origin IN ('web','channel')),
    source_channel   text,
    external_ref     text,
    total_amount     numeric(12,2) NOT NULL,
    commission_rate  numeric(5,4)   NOT NULL,
    commission_amt   numeric(12,2) NOT NULL,
    hold_expires_at  timestamptz,
    paid_at          timestamptz,
    cancelled_at     timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CHECK (checkout_date > checkin_date)
);

CREATE INDEX IF NOT EXISTS idx_booking_dates
    ON booking (unit_type_id, checkin_date, checkout_date)
    WHERE status IN ('hold','paid','confirmed');

CREATE TABLE IF NOT EXISTS booking_line (
    id          uuid          PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id  uuid          NOT NULL REFERENCES booking(id) ON DELETE CASCADE,
    date        date          NOT NULL,
    price       numeric(12,2) NOT NULL,
    UNIQUE (booking_id, date)
);
