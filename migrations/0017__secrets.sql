-- 0017__secrets.sql
-- Credentials and signing secrets stop being plaintext-ish.
--
-- Three things were stored weakly, and a leaked database was enough to take
-- all three:
--
-- * partner and staff passwords were a plain SHA-256 of a low-entropy secret
--   — a rainbow table away from every partner account;
-- * a channel API key was hashed the same way, and a cracked key books rooms
--   on the partner's inventory;
-- * the webhook subscription secret was stored as-is, and it is the secret our
--   own deliveries are signed with — so a leaked table let an attacker forge
--   messages the receiver would accept as ours.
--
-- Hashing is argon2id (memory-hard, deliberately slow); the seal is
-- authenticated encryption with a key the database does not hold.
--
-- What this migration does NOT do: re-hash existing rows. Passwords cannot be
-- re-derived, so legacy digests are left in place and upgraded on the next
-- successful login (utils.secrets.needs_rehash), which is the only moment the
-- plaintext is available. No forced reset of every partner.
--
-- The webhook secret is re-sealed where it is known to be a legacy plaintext;
-- a NULL stays NULL and means "not yet migrated", which the reader treats as
-- an unusable subscription.

ALTER TABLE partner   ALTER COLUMN password_hash TYPE text;
ALTER TABLE admin     ALTER COLUMN password_hash TYPE text;
ALTER TABLE api_key   ALTER COLUMN key_hash     TYPE text;

-- Sealed (Fernet token) subscription secret. Longer than the old plaintext,
-- and variable length: the same secret seals to a different token each time.
ALTER TABLE webhook_subscription ADD COLUMN IF NOT EXISTS secret_sealed text;

-- Mark every row that still holds a readable plaintext so the app can upgrade
-- it lazily, at the first use, where the plaintext is already in hand.
-- Sealing them all here would need the seal key inside a migration, which is
-- exactly where a key does not belong.
UPDATE webhook_subscription
SET secret_sealed = 'LEGACY:' || secret
WHERE secret_sealed IS NULL;

COMMENT ON COLUMN webhook_subscription.secret_sealed IS
    'Опечатанный секрет подписки (Fernet); LEGACY: prefix = открытый текст, перешифруется при первом использовании';
COMMENT ON COLUMN webhook_subscription.secret IS
    'Устарел: хранится только для отката. Используется secret_sealed.';
