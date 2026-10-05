-- 0022__webhook_secret_plaintext_gone.sql
--
-- The subscription secret signs every webhook we send, so a leaked table let
-- an attacker forge messages the receiver accepted as ours. 0017 added the
-- sealed column, but the INSERT still wrote the plaintext too, so the secret
-- stayed readable and the seal was only extra decoration.
--
-- Now the application writes only secret_sealed, and the plaintext column has
-- nothing left to do. Rows that still hold a plaintext are emptied; the
-- sealed column is authoritative. A NULL plaintext is not a rollback path
-- because nothing reads it anymore.

ALTER TABLE webhook_subscription ALTER COLUMN secret DROP NOT NULL;

UPDATE webhook_subscription
SET secret = NULL
WHERE secret IS NOT NULL;

COMMENT ON COLUMN webhook_subscription.secret IS
  'Удалён: секрет хранится только в secret_sealed. Колонка оставлена, чтобы не делать full-table rewrite в миграции.';
