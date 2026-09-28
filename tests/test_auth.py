"""Slice 0 tests: JWT issue/verify + auth service round-trip.

These run inside a rolled-back transaction (see conftest.py), so the partner
row never actually persists.
"""

from __future__ import annotations

import pytest

from app.modules.auth import service
from app.modules.auth.jwt import create_access_token, decode_access_token
from app.modules.auth.schemas import LoginRequest, PartnerRegisterRequest


def test_jwt_roundtrip() -> None:
    token = create_access_token("abc-123", scope="partner")
    data = decode_access_token(token)
    assert data is not None
    assert data.sub == "abc-123"
    assert data.scope == "partner"


def test_jwt_invalid_returns_none() -> None:
    assert decode_access_token("not.a.token") is None
    assert decode_access_token("") is None


def test_jwt_tampered_secret_fails() -> None:
    import jwt

    token = jwt.encode({"sub": "x", "scope": "partner"}, "wrong-secret", algorithm="HS256")
    assert decode_access_token(token) is None


@pytest.mark.asyncio
async def test_register_and_login(db_conn) -> None:
    req = PartnerRegisterRequest(email="t1@example.com", password="secret123", name="Tester")
    partner_id = await service.register_partner(db_conn, req)

    assert partner_id and len(partner_id) == 36  # uuid

    # login with correct password
    token = await service.login(db_conn, LoginRequest(email="t1@example.com", password="secret123"))
    assert decode_access_token(token) is not None

    # wrong password must fail
    with pytest.raises(ValueError):
        await service.login(db_conn, LoginRequest(email="t1@example.com", password="WRONG"))


@pytest.mark.asyncio
async def test_register_duplicate_email_raises(db_conn) -> None:
    req = PartnerRegisterRequest(email="t2@example.com", password="secret123", name="Tester")
    await service.register_partner(db_conn, req)
    with pytest.raises(ValueError):
        await service.register_partner(db_conn, req)


# ---- routes: the registration screen hits these over HTTP -----------------


def _client():
    from starlette.testclient import TestClient

    from app.main import create_app

    return TestClient(create_app())


@pytest.mark.asyncio
async def test_register_route_creates_and_issues_a_token(committed_conn) -> None:
    """The screen's happy path: 201, a token, and a row that can log in."""
    import uuid

    email = f"reg-{uuid.uuid4().hex[:8]}@example.com"
    with _client() as client:
        response = client.post(
            "/v1/auth/register",
            json={"email": email, "password": "secret123", "name": "Гостевой дом"},
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["scope"] == "partner"
    assert decode_access_token(body["access_token"]) is not None

    # The new account is usable immediately, with the argon2 hash in place.
    digest = await committed_conn.fetchval(
        "SELECT password_hash FROM partner WHERE email = $1", email
    )
    assert digest.startswith("$argon2id$")
    token = await service.login(committed_conn, LoginRequest(email=email, password="secret123"))
    assert decode_access_token(token) is not None


@pytest.mark.asyncio
async def test_register_route_rejects_a_duplicate_email(committed_conn) -> None:
    """An existing partner gets a 409 the screen can show as a sentence."""
    import uuid

    email = f"dup-{uuid.uuid4().hex[:8]}@example.com"
    await service.register_partner(
        committed_conn,
        PartnerRegisterRequest(email=email, password="secret123", name="Tester"),
    )

    with _client() as client:
        response = client.post(
            "/v1/auth/register",
            json={"email": email, "password": "secret123", "name": "Другой"},
        )

    assert response.status_code == 409
    assert "already registered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_route_rejects_a_short_password(committed_conn) -> None:
    """A password under the floor is a 422, never a silent account."""
    import uuid

    with _client() as client:
        response = client.post(
            "/v1/auth/register",
            json={
                "email": f"short-{uuid.uuid4().hex[:8]}@example.com",
                "password": "12345",
                "name": "Tester",
            },
        )

    assert response.status_code == 422
    # No account was created for the rejected request.
    assert (
        await committed_conn.fetchval("SELECT count(*) FROM partner WHERE email LIKE 'short-%'")
        == 0
    )
