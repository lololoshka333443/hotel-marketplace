from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.modules.auth.jwt import TokenData, decode_access_token

security = HTTPBearer(auto_error=True)


async def get_token_data(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> TokenData:
    token = credentials.credentials
    data = decode_access_token(token)
    if data is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")
    return data


def require_scope(*scopes: str):
    """FastAPI dependency: allow only tokens with one of the given scopes.

    Usage:
        @router.get("/partner/...", dependencies=[Depends(require_scope("partner"))])
    """

    async def _checker(data: Annotated[TokenData, Depends(get_token_data)]) -> TokenData:
        if data.scope not in scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"required scope: {scopes}",
            )
        return data

    return _checker
