from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer

from app.db.pool import get_pool
from app.modules.auth import service
from app.modules.auth.deps import require_scope
from app.modules.auth.jwt import TokenData, create_access_token
from app.modules.auth.schemas import LoginRequest, PartnerRegisterRequest, TokenResponse

router = APIRouter(prefix="/v1/auth", tags=["auth"])

security = HTTPBearer(auto_error=True)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: PartnerRegisterRequest) -> TokenResponse:
    """Register a new partner and immediately issue a token."""
    conn = await get_pool().acquire()
    try:
        try:
            partner_id = await service.register_partner(conn, data)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        token = create_access_token(partner_id, scope="partner")
        return TokenResponse(access_token=token, scope="partner", expires_in_min=60)
    finally:
        await get_pool().release(conn)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest) -> TokenResponse:
    conn = await get_pool().acquire()
    try:
        try:
            token = await service.login(conn, data)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials"
            ) from exc
        return TokenResponse(access_token=token, scope="partner", expires_in_min=60)
    finally:
        await get_pool().release(conn)


@router.get("/me")
async def me(
    token_data: Annotated[TokenData, Depends(require_scope("partner", "admin"))],
) -> dict:
    """Echo current token subject — used by the frontend to validate auth."""
    return {"sub": token_data.sub, "scope": token_data.scope}
