-- 0021__partner_telegram_chat_unique.sql
-- One chat, one partner.
--
-- 0020 gave the link code a UNIQUE index (so /start can never bind a chat to
-- the wrong partner) but left telegram_chat_id under a plain index. Nothing
-- stopped a second partner's /start from binding the same chat: both would
-- then receive that partner's bookings, and /unlink — which matches on the
-- chat alone — would drop the other partner's binding as a side effect.
--
-- UNIQUE here makes the overlap a hard error at the write itself. Partial
-- (`WHERE telegram_chat_id IS NOT NULL`), because unlinked partners all share
-- NULL and plain UNIQUE would treat them as one chat.

CREATE UNIQUE INDEX IF NOT EXISTS partner_telegram_chat_id_key
    ON partner (telegram_chat_id)
    WHERE telegram_chat_id IS NOT NULL;

COMMENT ON INDEX partner_telegram_chat_id_key IS 'One Telegram chat binds at most one partner; unlinked partners keep NULL without colliding';
