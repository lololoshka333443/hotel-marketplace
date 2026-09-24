-- 0008__commission.sql
-- Commission reporting + partner telegram binding.

ALTER TABLE partner ADD COLUMN IF NOT EXISTS telegram_chat_id text;

-- Denormalised commission snapshot: settled once a booking is confirmed so
-- reports never recompute money from potentially changing rules.
ALTER TABLE booking ADD COLUMN IF NOT EXISTS commission_status text
    NOT NULL DEFAULT 'none' CHECK (commission_status IN ('none','accrued','settled','void'));

-- Fast "who owes what" queries for the admin dashboard.
CREATE INDEX IF NOT EXISTS idx_booking_commission
    ON booking (commission_status, created_at)
    WHERE commission_status IN ('accrued','settled');
