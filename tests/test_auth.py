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
