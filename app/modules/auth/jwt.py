"""JWT issuing and verification.

Scopes: guest | partner | admin. The token carries the subject (partner_id or
guest id) and a scope that guards routers via `Depends(require_scope(...))`.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import jwt

from app.config.settings import settings


@dataclass(frozen=True)
class TokenData:
    sub: str
    scope: str


def create_access_token(sub: str, scope: str) -> str:
    now = dt.datetime.now(dt.UTC)
    payload = {
        "sub": sub,
        "scope": scope,
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(minutes=settings.access_token_ttl_min)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> TokenData | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return TokenData(sub=str(payload["sub"]), scope=str(payload["scope"]))
    except jwt.PyJWTError:
        return None
