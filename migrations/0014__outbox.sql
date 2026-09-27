-- 0014__outbox.sql
-- Outbox: we → external systems.
--
-- Every business event that a channel might want to know about is written to
-- outbox_event IN THE SAME TRANSACTION as the change it describes. A
-- background worker then delivers rows to the partner's webhook subscriptions.
-- This is the "we push out" half of Phase 3; iCal import / write-API were the
-- "pushed in" half.
--
-- Why a table and not a direct HTTP call in the request path: a webhook that
-- is slow or down must not make a booking fail, and an event must survive a
-- crash between "commit" and "send". The outbox row is the source of truth
-- for "did we tell them".

CREATE TABLE IF NOT EXISTS outbox_event (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    -- booking | rate_plan | inventory | property
    aggregate       text        NOT NULL,
    aggregate_id    text        NOT NULL,
    event_type      text        NOT NULL,
    payload         jsonb       NOT NULL DEFAULT '{}',
    -- The property the event is about; the worker joins it to the property's
    -- owner to find matching subscriptions. NULL only if resolution failed.
    property_id     uuid        REFERENCES property(id) ON DELETE SET NULL,
    -- pending | delivering | published | failed
    -- delivering is a claim: the worker owns it until it answers. A crashed
    -- worker leaves rows behind; the loop reclaims them after a timeout.
    status          text        NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','delivering','published','failed')),
    attempts        int         NOT NULL DEFAULT 0,
    max_attempts    int         NOT NULL DEFAULT 6,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    claimed_at      timestamptz,
    last_error      text,
    happened_at     timestamptz NOT NULL DEFAULT now(),
    published_at    timestamptz
);

CREATE INDEX IF NOT EXISTS idx_outbox_due
    ON outbox_event (next_attempt_at)
    WHERE status IN ('pending','delivering');

CREATE INDEX IF NOT EXISTS idx_outbox_status
    ON outbox_event (status, happened_at DESC);

CREATE TABLE IF NOT EXISTS webhook_subscription (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_id      uuid        NOT NULL REFERENCES partner(id) ON DELETE CASCADE,
    url             text        NOT NULL,
    -- event types this partner wants, e.g. {'booking.confirmed'}; '*' for all.
    event_types     text[]      NOT NULL NOT NULL DEFAULT '{*}',
    -- HMAC-SHA256 key the partner also configures on their side. Used to sign
    -- the body so the receiver can prove we sent it. Stored in plaintext for
    -- now; move to a sealed column / vault before production.
    secret          text        NOT NULL,
    enabled         boolean     NOT NULL DEFAULT true,
    last_delivery_at timestamptz,
    last_status     text,
    last_error      text,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_webhook_sub_partner
    ON webhook_subscription (partner_id)
    WHERE enabled;

-- Per-subscription delivery log: the reconciliation record. An event is
-- 'published' when every subscription it reached answered 2xx; a single flaky
-- subscriber does not block the others, because retries skip rows that
-- already succeeded.
CREATE TABLE IF NOT EXISTS webhook_delivery (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        uuid        NOT NULL REFERENCES outbox_event(id) ON DELETE CASCADE,
    subscription_id uuid        NOT NULL REFERENCES webhook_subscription(id) ON DELETE CASCADE,
    status          text        NOT NULL CHECK (status IN ('success','failed')),
    status_code     int,
    error           text,
    delivered_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (event_id, subscription_id)
);

COMMENT ON TABLE outbox_event IS 'События наружу: пишутся в той же транзакции, что и изменение';
COMMENT ON TABLE webhook_delivery IS 'Лог доставки события конкретной подписке — для reconciliation';
