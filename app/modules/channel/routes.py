"""Channel write-API routes.

Two audiences share this module:
- the channel itself (X-API-Key, /v1/channel/...);
- the partner managing its keys (JWT scope partner, /v1/partner/api-keys).
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.config.settings import settings
from app.db.pool import get_pool
from app.modules.auth.deps import require_scope
from app.modules.auth.jwt import TokenData
from app.modules.booking import service as booking_service
from app.modules.channel import schemas, service
from app.modules.payment import service as payment_service
from app.utils import ratelimit

router = APIRouter(prefix="/v1", tags=["channel"])


# ---- channel face ----------------------------------------------------------


async def _require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> dict:
    try:
        if x_api_key is None:
            raise service.KeyRejected("missing api key")
        conn = await get_pool().acquire()
        try:
            return await service.resolve_key(conn, x_api_key)
        finally:
            await get_pool().release(conn)
    except service.KeyRejected as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


async def _limit(
    key: Annotated[dict, Depends(_require_api_key)],
    *,
    bucket: str,
    limit: int,
) -> None:
    allowed, retry_after = await ratelimit.acquire(
        f"rl:channel:{bucket}:{key['id']}",
        limit,
        settings.rate_limit_window_sec,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate limit exceeded, retry later",
            headers={"Retry-After": str(retry_after)},
        )


async def _limit_read(key: Annotated[dict, Depends(_require_api_key)]) -> dict:
    """Read bucket: the channel reading tariffs and availability."""
    await _limit(key, bucket="read", limit=settings.channel_read_limit_per_min)
    return key


async def _limit_write(key: Annotated[dict, Depends(_require_api_key)]) -> dict:
    """Write bucket: a burst of invented bookings is the dangerous one."""
    await _limit(key, bucket="write", limit=settings.channel_write_limit_per_min)
    return key


@router.post("/channel/bookings", status_code=status.HTTP_201_CREATED)
async def create_channel_booking(
    data: schemas.ChannelBookingRequest,
    key: Annotated[dict, Depends(_limit_write)],
) -> dict:
    """Push a booking. Same path a guest takes: hold -> pay -> confirmed.

    The channel can only book its own partner's inventory, and never past a
    stop sell. A replay of idempotency_key returns the original booking.
    """
    pool = get_pool()
    conn = await pool.acquire()
    try:
        try:
            return await service.create_channel_booking(
                conn,
                partner_id=key["partner_id"],
                unit_type_id=data.unit_type_id,
                checkin=data.checkin,
                checkout=data.checkout,
                guest_name=data.guest.name,
                guest_email=str(data.guest.email),
                guest_phone=data.guest.phone,
                client_key=data.idempotency_key,
            )
        except service.NotOwned as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except booking_service.NotAvailable as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"dates not available: {exc}",
            ) from exc
        except booking_service.Conflict as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"idempotency conflict: {exc}",
            ) from exc
        except payment_service.PaymentError as exc:
            # The hold is released by the reaper; tell the channel to retry.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"confirmation failed: {exc}",
            ) from exc
    finally:
        await pool.release(conn)


@router.get("/channel/bookings/{booking_id}")
async def get_channel_booking(
    booking_id: str,
    key: Annotated[dict, Depends(_limit_read)],
) -> dict:
    """Read back a booking the channel pushed. Only channel-origin bookings."""
    conn = await get_pool().acquire()
    try:
        if not await service.booking_owned_by(conn, booking_id, key["partner_id"]):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="booking not found")
        row = await conn.fetchrow(
            """
            SELECT id::text, code, status, total_amount::float8,
                   checkin_date, checkout_date
            FROM booking WHERE id = $1
            """,
            booking_id,
        )
        assert row is not None
        return service.booking_out(row)
    finally:
        await get_pool().release(conn)


@router.post("/channel/bookings/{booking_id}/cancel")
async def cancel_channel_booking(
    booking_id: str,
    key: Annotated[dict, Depends(_limit_write)],
) -> dict:
    """Cancel what the channel pushed: a hold is released, a confirmed booking refunded."""
    conn = await get_pool().acquire()
    try:
        try:
            return await service.cancel_channel_booking(conn, key["partner_id"], booking_id)
        except service.NotOwned as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except service.NotAvailable as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except payment_service.PaymentError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    finally:
        await get_pool().release(conn)


@router.get("/channel/rates")
async def channel_rates(
    unit_type_id: Annotated[str, Query()],
    date_from: Annotated[dt.date, Query()],
    date_to: Annotated[dt.date, Query()],
    key: Annotated[dict, Depends(_limit_read)],
) -> dict:
    """Per-night tariffs for one unit type.

    The channel reads with the *same* API key it pushes bookings with, and only
    ever sees its own partner's inventory. Where the partner set no explicit
    price, the unit's base price applies. Half-open range: the checkout night
    is not priced.
    """
    pool = get_pool()
    conn = await pool.acquire()
    try:
        try:
            return await service.get_channel_rates(
                conn, key["partner_id"], unit_type_id, date_from, date_to
            )
        except service.NotOwned as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except service.BadRange as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            ) from exc
    finally:
        await pool.release(conn)


@router.get("/channel/availability")
async def channel_availability(
    unit_type_id: Annotated[str, Query()],
    date_from: Annotated[dt.date, Query()],
    date_to: Annotated[dt.date, Query()],
    key: Annotated[dict, Depends(_limit_read)],
) -> dict:
    """Per-night availability for one unit type.

    free = available - hold - sold. Closed dates (stop sell, including
    iCal-imported closures) are flagged and not bookable — the same rule that
    rejects a booking pushed on a closed date. Half-open range: checkout is not
    a stay.
    """
    pool = get_pool()
    conn = await pool.acquire()
    try:
        try:
            return await service.get_channel_availability(
                conn, key["partner_id"], unit_type_id, date_from, date_to
            )
        except service.NotOwned as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except service.BadRange as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            ) from exc
    finally:
        await pool.release(conn)


# ---- partner face ----------------------------------------------------------


@router.get("/partner/api-keys")
async def list_api_keys(
    token: Annotated[TokenData, Depends(require_scope("partner"))] = None,
) -> list[dict]:
    """Keys for the signed-in partner. Never includes the secret."""
    conn = await get_pool().acquire()
    try:
        return await service.list_keys(conn, token.sub)
    finally:
        await get_pool().release(conn)


@router.post("/partner/api-keys", status_code=status.HTTP_201_CREATED)
async def create_api_key(
    data: schemas.ApiKeyCreate,
    token: Annotated[TokenData, Depends(require_scope("partner"))] = None,
) -> dict:
    """Create a key. The plaintext is returned once and never again."""
    conn = await get_pool().acquire()
    try:
        return await service.create_key(conn, token.sub, data.label)
    finally:
        await get_pool().release(conn)


@router.delete("/partner/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    token: Annotated[TokenData, Depends(require_scope("partner"))] = None,
) -> dict:
    """Revoke a key. The bookings it created stay."""
    conn = await get_pool().acquire()
    try:
        revoked = await service.revoke_key(conn, token.sub, key_id)
        if not revoked:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="api key not found")
        return {"revoked": key_id}
    finally:
        await get_pool().release(conn)
