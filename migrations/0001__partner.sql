-- 0001__partner.sql
-- Partner account. Slice 0: auth + registration only.
-- Full profile fields (legal_type, phone) arrive in Slice 1.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS citext;

CREATE TABLE IF NOT EXISTS partner (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    email           citext      UNIQUE NOT NULL,
    password_hash   text        NOT NULL,
    name            text        NOT NULL,
    status          text        NOT NULL DEFAULT 'active'
                    CHECK (status IN ('pending','active','blocked')),
    created_at      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE partner IS 'Партнёр-размещенец (отель/хост)';
