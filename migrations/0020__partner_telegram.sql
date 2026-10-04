-- 0020__partner_telegram.sql
-- The partner's Telegram binding. The chat id is what notify_booking_confirmed
-- already reads; until now nothing could write it, so the bot column sat empty.
--
-- Linking goes through a one-time code, not the chat id: the partner takes the
-- code from the cabinet, sends /start <code> to the bot, and the bot stores the
-- chat this message came from. The code is a secret the partner copies, and it
-- rotates on every use, so a leaked screenshot of the cabinet cannot bind a
-- stranger's chat to someone's notifications.
--
-- UNIQUE on the code: two partners must never share a linking code, or /start
-- would bind the chat to the wrong one. The index on telegram_chat_id keeps the
-- partner lookup in the notification path an index read.

ALTER TABLE partner ADD COLUMN IF NOT EXISTS telegram_link_code text
    NOT NULL DEFAULT gen_random_uuid()::text;
ALTER TABLE partner ADD COLUMN IF NOT EXISTS telegram_linked_at timestamptz;

CREATE UNIQUE INDEX IF NOT EXISTS partner_telegram_link_code_key
    ON partner (telegram_link_code);
CREATE INDEX IF NOT EXISTS idx_partner_telegram_chat_id
    ON partner (telegram_chat_id);

COMMENT ON COLUMN partner.telegram_link_code IS 'One-time code the partner sends to the bot as /start <code>; rotates after a successful link';
COMMENT ON COLUMN partner.telegram_linked_at IS 'When the chat id was bound; NULL while the partner has not linked a chat';
