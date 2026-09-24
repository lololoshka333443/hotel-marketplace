-- 0006__payment.sql
-- Payment record. Phase 1 uses the stub provider; real acquiring plugs in
-- later by implementing the same PaymentProvider protocol.

CREATE TABLE IF NOT EXISTS payment (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id      uuid        NOT NULL REFERENCES booking(id),
    provider        text        NOT NULL DEFAULT 'stub'
                    CHECK (provider IN ('stub','fail','tinkoff','yookassa')),
    external_id     text,
    amount          numeric(12,2) NOT NULL CHECK (amount >= 0),
    status          text        NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','succeeded','failed','refunded')),
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_payment_booking ON payment (booking_id);
