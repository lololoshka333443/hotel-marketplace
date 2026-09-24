"""Auth service: registers partners, issues JWTs.

Slice 0 keeps this intentionally simple — password hash + token. Partner
profile fields (legal_type, phone…) come in Slice 1.

All functions take an `asyncpg.Connection` so tests can pass a transaction
that is rolled back afterwards.
"""

from __future__ import annotations

import asyncpg

from app.modules.auth.jwt import create_access_token
from app.modules.auth.schemas import LoginRequest, PartnerRegisterRequest
from app.utils.logger import get_logger

log = get_logger(__name__)


def _hash_password(raw: str) -> str:
    import hashlib

    # Slice 0 placeholder: move to bcrypt/argon2 before any real user.
    return hashlib.sha256(raw.encode()).hexdigest()


async def register_partner(conn: asyncpg.Connection, data: PartnerRegisterRequest) -> str:
    """Create a partner row, return new partner id (uuid string)."""
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO partner (email, password_hash, name)
            VALUES ($1, $2, $3)
            RETURNING id::text
            """,
            data.email,
            _hash_password(data.password),
            data.name,
        )
        return row["id"]
    except asyncpg.UniqueViolationError as exc:
        raise ValueError("email already registered") from exc


async def login(conn: asyncpg.Connection, data: LoginRequest) -> str:
    """Verify credentials, return JWT."""
    row = await conn.fetchrow(
        "SELECT id::text, password_hash FROM partner WHERE email = $1", data.email
    )
    if row is None or row["password_hash"] != _hash_password(data.password):
        raise ValueError("invalid credentials")

    log.info("partner-login", partner_id=row["id"])
    return create_access_token(row["id"], scope="partner")
