-- 0010__admin.sql
-- Marketplace admin (staff) accounts. Separate from partner: staff tokens carry
-- scope 'admin' and reach /v1/admin/* (reports, moderation).

CREATE TABLE IF NOT EXISTS admin (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    email           citext      UNIQUE NOT NULL,
    password_hash   text        NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE admin IS 'Сотрудник маркетплейса (модерация, отчёты)';
