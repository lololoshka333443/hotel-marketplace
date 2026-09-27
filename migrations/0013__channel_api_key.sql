-- 0013__channel_api_key.sql
-- Channel write-API credentials.
--
-- A channel (OTA, channel manager) pushes bookings into us through
-- POST /v1/channel/bookings using an API key instead of a JWT. The key is a
-- partner-scoped secret: it can only touch that partner's inventory.
--
-- Only the hash is stored; the plaintext is shown to the partner exactly once
-- at creation (same as the iCal feed token). key_prefix is the visible part
-- that identifies a key in the UI ("hm_live_3f9a…").
--
-- NOTE: SHA-256 matches the current password storage. Both move to argon2
-- before production.

CREATE TABLE IF NOT EXISTS api_key (
    id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    partner_id   uuid        NOT NULL REFERENCES partner(id) ON DELETE CASCADE,
    label        text        NOT NULL CHECK (length(label) >= 2),
    key_hash     text        NOT NULL UNIQUE,
    key_prefix   text        NOT NULL,
    enabled      boolean     NOT NULL DEFAULT true,
    last_used_at timestamptz,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_api_key_partner
    ON api_key (partner_id)
    WHERE enabled;

COMMENT ON TABLE api_key IS 'API-ключ канала: толкает брони в нас через write-API';
