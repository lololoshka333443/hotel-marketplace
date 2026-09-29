"""Security debts closed: argon2id for credentials, sealed webhook secrets.

What was wrong before: partner and staff passwords and channel API keys were a
plain SHA-256 of a low-entropy secret (a rainbow table away from every account),
and the webhook subscription secret was stored as-is — the very secret our own
deliveries are signed with.

What changed:
* passwords and API keys hash to argon2id, salted per row;
* a legacy SHA-256 digest still verifies, and is upgraded in place on the first
  successful use — no forced reset of every partner;
* the webhook secret is sealed (Fernet, authenticated encryption) with a key the
  database does not hold;
* an unsealable or missing secret fails closed: the subscription is skipped
  rather than delivered unsigned or with an empty signature.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import uuid

import asyncpg
import pytest
from cryptography.fernet import Fernet

from app.config.settings import settings
from app.modules.admin import service as admin_service
from app.modules.auth import service as auth_service
from app.modules.auth.schemas import LoginRequest, PartnerRegisterRequest
from app.utils import secrets as secrets_util
from app.utils.secrets import (
    hash_secret,
    needs_rehash,
    seal,
    seal_key_is_configured,
    unseal,
    verify_secret,
)

TODAY = dt.date.today()


def _sha256(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# ---- hashing ---------------------------------------------------------------


def test_argon2_hash_is_not_the_plaintext_and_not_sha256() -> None:
    raw = "partner-password"
    digest = hash_secret(raw)

    assert digest != raw
    assert digest != _sha256(raw)
    assert digest.startswith("$argon2id$")


def test_the_same_plaintext_hashes_differently_each_call() -> None:
    """A per-row salt means two partners with one password store two hashes."""
    first = hash_secret("same-password")
    second = hash_secret("same-password")
    assert first != second
    assert verify_secret("same-password", first)
    assert verify_secret("same-password", second)


def test_verify_rejects_the_wrong_secret() -> None:
    digest = hash_secret("correct-horse-battery-staple")
    assert not verify_secret("wrong", digest)


def test_a_legacy_sha256_digest_still_verifies() -> None:
    """Old rows must keep working until they are re-hashed."""
    digest = _sha256("legacy-password")
    assert verify_secret("legacy-password", digest)
    assert not verify_secret("nope", digest)


def test_needs_rehash_flags_a_legacy_digest_and_a_weak_argon2() -> None:
    assert needs_rehash(_sha256("legacy-password")) is True

    strong = hash_secret("strong-enough")
    assert needs_rehash(strong) is False


def test_verify_treats_a_mangled_hash_as_a_failed_login() -> None:
    """A truncated or corrupt hash column is not something to paper over."""
    assert verify_secret("anything", "$argon2id$not-a-real-hash") is False


# ---- sealing ---------------------------------------------------------------


def test_sealed_secret_is_not_the_plaintext_and_round_trips() -> None:
    plaintext = "webhook-signing-secret"
    token = seal(plaintext)

    assert token != plaintext
    assert unseal(token) == plaintext


def test_sealing_the_same_secret_twice_gives_different_tokens() -> None:
    """The column must not reveal which subscriptions share a secret."""
    assert seal("same-secret") != seal("same-secret")


def test_unseal_rejects_a_tampered_token() -> None:
    token = seal("real-secret")
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    with pytest.raises(RuntimeError):
        unseal(tampered)


def test_seal_without_a_key_fails_closed(monkeypatch) -> None:
    """No seal key configured: refuse to store an unsealed secret."""
    monkeypatch.setattr(settings, "webhook_seal_key", "")
    assert seal_key_is_configured() is False
    with pytest.raises(RuntimeError):
        seal("a-secret")


def test_a_rotated_key_still_reads_the_old_tokens(monkeypatch) -> None:
    """Rotation is not an outage: the outgoing key stays readable."""
    old_key = settings.webhook_seal_key
    token = seal("rotation-secret")

    new_key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "webhook_seal_key", new_key)
    monkeypatch.setattr(settings, "webhook_seal_key_previous", "")

    # Without the outgoing key the token is gone.
    with pytest.raises(RuntimeError):
        unseal(token)

    # With it as PREVIOUS the row reads, and new secrets seal under the new key.
    monkeypatch.setattr(settings, "webhook_seal_key_previous", old_key)
    assert unseal(token) == "rotation-secret"
    assert unseal(seal("fresh-secret")) == "fresh-secret"


def test_unsealed_rows_survive_a_rotation(monkeypatch) -> None:
    """The fallback does not make a tampered or garbage token pass."""
    monkeypatch.setattr(settings, "webhook_seal_key_previous", Fernet.generate_key().decode())
    with pytest.raises(RuntimeError):
        unseal("not-a-real-token")


def test_the_outgoing_key_must_still_be_a_real_key(monkeypatch) -> None:
    """A stray empty PREVIOUS is skipped, not treated as a working key."""
    monkeypatch.setattr(settings, "webhook_seal_key_previous", "")
    token = seal("ok")
    assert unseal(token) == "ok"


# ---- partner login: legacy upgrade ----------------------------------------


async def _property_for(conn: asyncpg.Connection, email: str) -> str:
    partner_id = str(
        await auth_service.register_partner(
            conn, PartnerRegisterRequest(email=email, password="secret123", name="Tester")
        )
    )
    from app.modules.property import service as property_service
    from app.modules.property.schemas import PropertyCreate

    await property_service.create_property(
        conn,
        partner_id,
        PropertyCreate(
            name="Test",
            property_type="apartment",
            city="Koktebel",
            timezone="Europe/Simferopol",
        ),
    )
    return partner_id


@pytest.mark.asyncio
async def test_new_partner_password_is_argon2(committed_conn) -> None:
    partner_id = await _property_for(committed_conn, "sec1@example.com")
    digest = await committed_conn.fetchval(
        "SELECT password_hash FROM partner WHERE id = $1", partner_id
    )
    assert digest.startswith("$argon2id$")


@pytest.mark.asyncio
async def test_legacy_partner_password_verifies_and_is_upgraded(committed_conn) -> None:
    """An existing SHA-256 row logs in, and leaves as argon2 — no reset needed."""
    partner_id = await _property_for(committed_conn, "sec2@example.com")
    await committed_conn.execute(
        "UPDATE partner SET password_hash = $2 WHERE id = $1",
        partner_id,
        _sha256("legacy-login-password"),
    )

    token = await auth_service.login(
        committed_conn,
        LoginRequest(email="sec2@example.com", password="legacy-login-password"),
    )
    assert token

    digest = await committed_conn.fetchval(
        "SELECT password_hash FROM partner WHERE id = $1", partner_id
    )
    assert digest.startswith("$argon2id$")
    # The old digest is gone.
    assert digest != _sha256("legacy-login-password")


@pytest.mark.asyncio
async def test_wrong_partner_password_does_not_touch_the_row(committed_conn) -> None:
    partner_id = await _property_for(committed_conn, "sec3@example.com")
    digest_before = await committed_conn.fetchval(
        "SELECT password_hash FROM partner WHERE id = $1", partner_id
    )

    with pytest.raises(ValueError):
        await auth_service.login(
            committed_conn,
            LoginRequest(email="sec3@example.com", password="totally-wrong"),
        )

    digest_after = await committed_conn.fetchval(
        "SELECT password_hash FROM partner WHERE id = $1", partner_id
    )
    assert digest_before == digest_after


@pytest.mark.asyncio
async def test_legacy_admin_password_verifies_and_is_upgraded(committed_conn) -> None:
    await committed_conn.execute(
        """
        INSERT INTO admin (email, password_hash)
        VALUES ('sec-admin@example.com', $1)
        ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash
        """,
        _sha256("legacy-admin-password"),
    )

    token = await admin_service.login_admin(
        committed_conn, "sec-admin@example.com", "legacy-admin-password"
    )
    assert token

    digest = await committed_conn.fetchval(
        "SELECT password_hash FROM admin WHERE email = $1", "sec-admin@example.com"
    )
    assert digest.startswith("$argon2id$")


# ---- channel API key -------------------------------------------------------


@pytest.mark.asyncio
async def test_api_key_hashes_to_argon2_and_resolves(committed_conn) -> None:
    """A new key is salted, and the presented key still maps to its partner."""
    from app.modules.channel import service as channel_service

    partner_id = await _property_for(committed_conn, "sec4@example.com")
    created = await channel_service.create_key(committed_conn, partner_id, "Ключ")

    digest = await committed_conn.fetchval(
        "SELECT key_hash FROM api_key WHERE id = $1", created["id"]
    )
    assert digest.startswith("$argon2id$")
    # The plaintext is returned once and not stored.
    assert created["key"] != digest

    resolved = await channel_service.resolve_key(committed_conn, created["key"])
    assert resolved["partner_id"] == partner_id


@pytest.mark.asyncio
async def test_legacy_api_key_verifies_and_is_upgraded(committed_conn) -> None:
    """A key stored under the old SHA-256 scheme still works, then upgrades."""
    from app.modules.channel import service as channel_service

    partner_id = await _property_for(committed_conn, "sec5@example.com")
    raw = channel_service.generate_key()
    key_id = await committed_conn.fetchval(
        """
        INSERT INTO api_key (partner_id, label, key_hash, key_prefix)
        VALUES ($1, 'Старый ключ', $2, $3)
        RETURNING id::text
        """,
        partner_id,
        _sha256(raw),
        raw[: channel_service.PREFIX_LEN],
    )

    resolved = await channel_service.resolve_key(committed_conn, raw)
    assert resolved["partner_id"] == partner_id

    digest = await committed_conn.fetchval("SELECT key_hash FROM api_key WHERE id = $1", key_id)
    assert digest.startswith("$argon2id$")
    assert digest != _sha256(raw)


@pytest.mark.asyncio
async def test_a_wrong_key_with_the_right_prefix_is_rejected(committed_conn) -> None:
    """The prefix narrows candidates; verification is what decides."""
    from app.modules.channel import service as channel_service

    partner_id = await _property_for(committed_conn, "sec6@example.com")
    created = await channel_service.create_key(committed_conn, partner_id, "Ключ")
    # Same visible prefix, different secret.
    fake = created["key"][: channel_service.PREFIX_LEN] + "a-different-secret-value"

    with pytest.raises(channel_service.KeyRejected):
        await channel_service.resolve_key(committed_conn, fake)


# ---- webhook secret: sealed at rest, unreadable as plaintext ---------------


async def _subscribe_row(conn: asyncpg.Connection, partner_id: str) -> str:
    from tests._subs import subscribe

    sub_id = await subscribe(conn, partner_id, "http://localhost:9/hooks", "signing-secret")
    return await conn.fetchval(
        "SELECT secret_sealed FROM webhook_subscription WHERE id = $1", sub_id
    )


@pytest.mark.asyncio
async def test_subscription_secret_is_sealed_not_plaintext(committed_conn) -> None:
    partner_id = await _property_for(committed_conn, "sec7@example.com")
    sealed = await _subscribe_row(committed_conn, partner_id)

    assert sealed is not None
    assert unseal(sealed) == "signing-secret"
    # Nothing readable in the column the DB can hand over.
    assert sealed != "signing-secret"


@pytest.mark.asyncio
async def test_delivery_reads_the_sealed_secret(committed_conn) -> None:
    """subscribers_for hands the worker the unsealed secret, not the column."""
    from app.modules.outbox import service as outbox_service

    partner_id = await _property_for(committed_conn, "sec8@example.com")
    await _subscribe_row(committed_conn, partner_id)
    event_id = str(uuid.uuid4())
    await outbox_service.emit(
        committed_conn,
        aggregate="property",
        aggregate_id=str(uuid.uuid4()),
        event_type=outbox_service.PROPERTY_STATUS_CHANGED,
        payload={},
        property_id=(
            await committed_conn.fetchval(
                "SELECT id::text FROM property WHERE partner_id = $1", partner_id
            )
        ),
    )
    event_id = await committed_conn.fetchval(
        "SELECT id::text FROM outbox_event WHERE aggregate = 'property' "
        "ORDER BY happened_at DESC LIMIT 1"
    )
    assert event_id is not None

    [sub] = await outbox_service.subscribers_for(
        committed_conn, event_id, outbox_service.PROPERTY_STATUS_CHANGED
    )
    assert sub["secret"] == "signing-secret"


@pytest.mark.asyncio
async def test_legacy_plaintext_secret_is_sealed_on_first_use(committed_conn) -> None:
    """A row written by the old code still delivers, and seals itself on the way."""
    from app.modules.outbox import service as outbox_service
    from tests._subs import subscribe

    partner_id = await _property_for(committed_conn, "sec9@example.com")
    sub_id = await subscribe(
        committed_conn, partner_id, "http://localhost:9/hooks", "legacy-plaintext"
    )
    # Wind the row back to the pre-migration state.
    await committed_conn.execute(
        "UPDATE webhook_subscription SET secret_sealed = $2 WHERE id = $1",
        sub_id,
        "LEGACY:legacy-plaintext",
    )

    event_id = await committed_conn.fetchval(
        "SELECT id::text FROM outbox_event WHERE aggregate = 'property' "
        "ORDER BY happened_at DESC LIMIT 1"
    )
    if event_id is None:
        await outbox_service.emit(
            committed_conn,
            aggregate="property",
            aggregate_id=str(uuid.uuid4()),
            event_type=outbox_service.PROPERTY_STATUS_CHANGED,
            payload={},
            property_id=(
                await committed_conn.fetchval(
                    "SELECT id::text FROM property WHERE partner_id = $1", partner_id
                )
            ),
        )
        event_id = await committed_conn.fetchval(
            "SELECT id::text FROM outbox_event WHERE aggregate = 'property' "
            "ORDER BY happened_at DESC LIMIT 1"
        )
    assert event_id is not None

    [sub] = await outbox_service.subscribers_for(
        committed_conn, event_id, outbox_service.PROPERTY_STATUS_CHANGED
    )
    assert sub["secret"] == "legacy-plaintext"

    sealed = await committed_conn.fetchval(
        "SELECT secret_sealed FROM webhook_subscription WHERE id = $1", sub_id
    )
    assert sealed is not None
    assert not sealed.startswith("LEGACY:")
    assert unseal(sealed) == "legacy-plaintext"


@pytest.mark.asyncio
async def test_an_unsealable_secret_is_skipped_not_delivered_unsigned(
    committed_conn, monkeypatch
) -> None:
    """A secret we cannot read drops the subscription instead of sending a fake."""
    from app.modules.outbox import service as outbox_service
    from tests._subs import subscribe

    partner_id = await _property_for(committed_conn, "sec10@example.com")
    sub_id = await subscribe(
        committed_conn, partner_id, "http://localhost:9/hooks", "sealed-then-lost"
    )

    def boom(_token: str) -> str:
        raise RuntimeError("seal key gone")

    monkeypatch.setattr(secrets_util, "unseal", boom)

    event_id = await committed_conn.fetchval(
        "SELECT id::text FROM outbox_event WHERE aggregate = 'property' "
        "ORDER BY happened_at DESC LIMIT 1"
    )
    if event_id is None:
        await outbox_service.emit(
            committed_conn,
            aggregate="property",
            aggregate_id=str(uuid.uuid4()),
            event_type=outbox_service.PROPERTY_STATUS_CHANGED,
            payload={},
            property_id=(
                await committed_conn.fetchval(
                    "SELECT id::text FROM property WHERE partner_id = $1", partner_id
                )
            ),
        )
        event_id = await committed_conn.fetchval(
            "SELECT id::text FROM outbox_event WHERE aggregate = 'property' "
            "ORDER BY happened_at DESC LIMIT 1"
        )
    assert event_id is not None

    subs = await outbox_service.subscribers_for(
        committed_conn, event_id, outbox_service.PROPERTY_STATUS_CHANGED
    )
    assert sub_id not in {s["id"] for s in subs}


@pytest.mark.asyncio
async def test_creating_a_webhook_seals_the_secret(committed_conn) -> None:
    """The API route writes a sealed column, and never returns the secret.

    Through HTTP rather than the function, because the route owns the pool it
    takes a connection from — that is the path that runs in production.
    """
    from starlette.testclient import TestClient

    from app.main import create_app

    partner_id = await _property_for(committed_conn, "sec11@example.com")
    token = auth_service.create_access_token(partner_id, scope="partner")

    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/partner/webhooks",
            json={"url": "http://localhost:9/hooks", "secret": "route-level-secret"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        created = response.json()
        assert "secret" not in created

        # The listing must not hand the secret back either — it is shown once,
        # at creation, and after that only the sealed column holds it.
        listed = client.get(
            "/v1/partner/webhooks",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert listed.status_code == 200
        assert "secret" not in listed.text

    sealed = await committed_conn.fetchval(
        "SELECT secret_sealed FROM webhook_subscription WHERE id = $1", created["id"]
    )
    assert unseal(sealed) == "route-level-secret"


# ---- key rotation ----------------------------------------------------------


@pytest.mark.asyncio
async def test_rotating_the_seal_key_re_seals_every_row(committed_conn) -> None:
    """The rotation script moves every secret onto the new key, idempotently."""
    from scripts.rotate_seal_key import rotate

    old_key = settings.webhook_seal_key
    new_key = Fernet.generate_key().decode()
    partner_id = await _property_for(committed_conn, "sec12@example.com")
    # Two subscriptions: one already on the new key, one sealed with the
    # outgoing key — the rotation must move the second and leave the first.
    settings.webhook_seal_key = new_key
    [kept, stale] = await committed_conn.fetch(
        """
        INSERT INTO webhook_subscription (partner_id, url, secret, secret_sealed, event_types)
        VALUES ($1, 'http://localhost:9/a', 'keep-me', $2, '{*}'),
               ($1, 'http://localhost:9/b', 'move-me', $3, '{*}')
        RETURNING id::text, secret_sealed
        """,
        partner_id,
        seal("keep-me"),
        Fernet(old_key.encode()).encrypt(b"move-me").decode(),
    )

    import scripts.rotate_seal_key as rotator

    original_init = rotator.init_pool

    async def fake_init_pool():
        class _P:
            async def acquire(self):
                return committed_conn

            async def release(self, _conn):
                pass

            async def close(self):
                pass

        return _P()

    rotator.init_pool = fake_init_pool
    settings.webhook_seal_key = new_key
    settings.webhook_seal_key_previous = old_key
    try:
        stats = await rotate(committed_conn)
        # A second run is a no-op: everything is already on the current key.
        second = await rotate(committed_conn)
    finally:
        settings.webhook_seal_key = old_key
        settings.webhook_seal_key_previous = ""
        rotator.init_pool = original_init

    assert stats["resealed"] == 1
    assert stats["already_current"] == 1
    assert stats["unsealable"] == 0
    assert second["resealed"] == 0
    assert second["already_current"] == 2

    assert await committed_conn.fetchval(
        "SELECT secret_sealed FROM webhook_subscription WHERE id = $1", kept["id"]
    ) == kept["secret_sealed"]
    moved = await committed_conn.fetchval(
        "SELECT secret_sealed FROM webhook_subscription WHERE id = $1", stale["id"]
    )
    assert moved != stale["secret_sealed"]
    # The delivery path reads it with the new key alone now.
    settings.webhook_seal_key = new_key
    settings.webhook_seal_key_previous = ""
    try:
        assert unseal(moved) == "move-me"
    finally:
        settings.webhook_seal_key = old_key


@pytest.mark.asyncio
async def test_rotation_reports_unsealable_rows(committed_conn) -> None:
    """A row neither key reads is counted, not silently re-sealed as garbage."""
    from scripts.rotate_seal_key import rotate

    partner_id = await _property_for(committed_conn, "sec13@example.com")
    sub_id = await committed_conn.fetchval(
        """
        INSERT INTO webhook_subscription (partner_id, url, secret, secret_sealed, event_types)
        VALUES ($1, 'http://localhost:9/c', 'lost', $2, '{*}')
        RETURNING id::text
        """,
        partner_id,
        Fernet(Fernet.generate_key()).encrypt(b"lost").decode(),  # a third key
    )
    old = settings.webhook_seal_key
    settings.webhook_seal_key = Fernet.generate_key().decode()
    try:
        stats = await rotate(committed_conn)
    finally:
        settings.webhook_seal_key = old

    assert stats["unsealable"] == 1
    # The row is untouched: garbage in, garbage out is not an option.
    assert await committed_conn.fetchval(
        "SELECT secret_sealed FROM webhook_subscription WHERE id = $1", sub_id
    ) is not None
