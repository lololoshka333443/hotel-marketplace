-- 0002__property.sql
-- Property (объект размещения)..partner leads it in our cabinet; the public
-- catalog sees only status='published'.

CREATE TABLE IF NOT EXISTS property (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_id      uuid        NOT NULL REFERENCES partner(id) ON DELETE CASCADE,
    name            text        NOT NULL,
    slug            text        UNIQUE,
    property_type   text        NOT NULL
                    CHECK (property_type IN ('hotel','apartment','house','room','hostel')),
    city            text        NOT NULL DEFAULT '',
    timezone        text        NOT NULL,
    checkin_time    time        NOT NULL DEFAULT '14:00',
    checkout_time   time        NOT NULL DEFAULT '12:00',
    currency        text        NOT NULL DEFAULT 'RUB',
    status          text        NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft','pending_moderation','published','blocked')),
    lat             double precision,
    lng             double precision,
    address         jsonb       NOT NULL DEFAULT '{}',
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_property_partner ON property (partner_id);
CREATE INDEX IF NOT EXISTS idx_property_status  ON property (status);
CREATE INDEX IF NOT EXISTS idx_property_city    ON property (city);

COMMENT ON TABLE property IS 'Объект размещения (квартира/апарт/комната/дом/отель)';
